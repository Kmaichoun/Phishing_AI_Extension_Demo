"""Extend tree input width without modifying learned splits or probabilities.

New schemas must preserve the original ordered feature prefix. Rebuild Tree
through its serialization state; this depends on the installed sklearn version
and is verified against original predictions before use. No fitting here.
"""
import copy
from sklearn.tree import _tree


def extend_forest(forest, old_names, new_names):
    if new_names[:len(old_names)] != old_names or len(old_names) != forest.n_features_in_:
        raise ValueError('Original feature prefix must be preserved exactly')
    extended = copy.copy(forest)
    extended.n_features_in_ = len(new_names)
    extended.estimators_ = []
    for original in forest.estimators_:
        estimator = copy.copy(original)
        estimator.n_features_in_ = len(new_names)
        estimator.tree_ = _tree.Tree(len(new_names), original.tree_.n_classes, original.n_outputs_)
        estimator.tree_.__setstate__(original.tree_.__getstate__())
        extended.estimators_.append(estimator)
    return extended
