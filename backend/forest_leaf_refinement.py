"""Experimental, data-learned refinement of existing RF terminal nodes.

The original forest remains the backbone. Small classification trees learn
additional splits inside its leaves from development training data. Only pure
benign descendants with adequate support and no positive guard observations
can replace a leaf probability; other descendants retain the original value.
There are no URL strings, domain allowlists, or brand score overrides here.
This is a custom incremental training procedure, not sklearn's ordinary fit.
"""
from __future__ import annotations

import copy
import numpy as np
from sklearn.tree import DecisionTreeClassifier, _tree


def learn_regions(estimator, train_x, train_y, hard_negative, guard_x, guard_y,
                  seed, depth=4, min_leaf=4, columns=None):
    train_leaves = estimator.apply(train_x)
    guard_leaves = estimator.apply(guard_x)
    order = np.argsort(train_leaves, kind='stable')
    leaves, start, count = np.unique(train_leaves[order], return_index=True, return_counts=True)
    regions = []
    for leaf, offset, size in zip(leaves, start, count):
        values = estimator.tree_.value[leaf, 0]
        old_p = float(values[1] / values.sum())
        indices = order[offset:offset + size]
        if old_p < .35 or size < 16 or hard_negative[indices].sum() < 2:
            continue
        y = train_y[indices]
        if set(np.unique(y)) != {0, 1}:
            # A completely benign region is still data-learned; the constant
            # classifier has no class 1 column, so handle its counts explicitly.
            if np.any(y == 1):
                continue
        tree = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=min_leaf,
                                      class_weight='balanced', random_state=seed)
        training = train_x[indices]
        tree.fit(training if columns is None else training[:, columns], y)
        if columns is not None:
            state = tree.tree_.__getstate__()
            mapped = state['nodes'].copy()
            split = mapped['feature'] >= 0
            mapped['feature'][split] = np.asarray(columns)[mapped['feature'][split]]
            expanded = _tree.Tree(train_x.shape[1], tree.tree_.n_classes, tree.n_outputs_)
            expanded.__setstate__({**state, 'nodes': mapped})
            tree.tree_ = expanded
            tree.n_features_in_ = train_x.shape[1]
        gx = guard_x[(guard_leaves == leaf) & (guard_y == 1)]
        protected = np.asarray(tree.decision_path(gx).sum(axis=0)).ravel() if len(gx) else np.zeros(tree.tree_.node_count)
        positive_column = list(tree.classes_).index(1) if 1 in tree.classes_ else None
        pure = np.ones(tree.tree_.node_count, dtype=bool) if positive_column is None else tree.tree_.value[:, 0, positive_column] == 0
        pure &= protected == 0
        if np.any(pure & (tree.tree_.n_node_samples >= min_leaf)):
            regions.append((int(leaf), tree, pure))
    return regions


def refine_estimator(estimator, regions, depth, minimum_support, required_feature=None):
    old_state = estimator.tree_.__getstate__()
    nodes = [n.copy() for n in old_state['nodes']]
    values = [v.copy() for v in old_state['values']]
    changed = 0
    for old_leaf, regional, pure in regions:
        rt = regional.tree_
        regional_nodes = rt.__getstate__()['nodes']
        original_value = old_state['values'][old_leaf].copy()
        old_p = float(original_value[0, 1] / original_value.sum())

        def plan(node, level, required_branch=False):
            n = int(rt.n_node_samples[node])
            if pure[node] and n >= minimum_support and 1 / (n + 2) < old_p and (required_feature is None or required_branch):
                return ('benign', node, n)
            if level >= depth or rt.children_left[node] == _tree.TREE_LEAF:
                return None
            left = plan(rt.children_left[node], level + 1, required_branch)
            true_branch = required_branch or (rt.feature[node] == required_feature and 0 <= rt.threshold[node] < 1)
            right = plan(rt.children_right[node], level + 1, true_branch)
            return ('split', node, left, right) if left is not None or right is not None else None

        planned = plan(0, 0)
        if planned is None:
            continue
        changed += 1

        def write(item, target):
            if item is None:
                n = old_state['nodes'][old_leaf].copy()
                n['left_child'] = n['right_child'] = _tree.TREE_LEAF
                n['feature'] = _tree.TREE_UNDEFINED
                n['threshold'] = _tree.TREE_UNDEFINED
                nodes[target] = n
                values[target] = original_value.copy()
                return
            n = regional_nodes[item[1]].copy()
            nodes[target] = n
            values[target] = original_value.copy()
            if item[0] == 'benign':
                p = 1 / (item[2] + 2)  # Laplace estimate from pure training observations.
                values[target][0] = np.array([1 - p, p]) * original_value.sum()
                n['left_child'] = n['right_child'] = _tree.TREE_LEAF
                n['feature'] = _tree.TREE_UNDEFINED
                n['threshold'] = _tree.TREE_UNDEFINED
                nodes[target] = n
                return
            left = len(nodes)
            nodes.extend([n.copy(), n.copy()])
            values.extend([original_value.copy(), original_value.copy()])
            nodes[target]['left_child'] = left
            nodes[target]['right_child'] = left + 1
            write(item[2], left)
            write(item[3], left + 1)

        write(planned, old_leaf)
    array = np.asarray(nodes, dtype=old_state['nodes'].dtype)
    val = np.asarray(values, dtype=old_state['values'].dtype)
    max_depth, stack = 0, [(0, 0)]
    while stack:
        node, level = stack.pop()
        max_depth = max(max_depth, level)
        if array[node]['left_child'] != _tree.TREE_LEAF:
            stack.extend([(int(array[node]['left_child']), level + 1), (int(array[node]['right_child']), level + 1)])
    result = copy.copy(estimator)
    result.tree_ = _tree.Tree(estimator.n_features_in_, estimator.tree_.n_classes, estimator.n_outputs_)
    result.tree_.__setstate__({'max_depth': max_depth, 'node_count': len(array), 'nodes': array, 'values': val})
    return result, changed
