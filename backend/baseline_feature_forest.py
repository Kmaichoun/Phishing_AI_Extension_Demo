"""RF classifier with an additional learned baseline-RF probability feature.

The baseline forest uses only the original ordered URL-feature prefix. The final
classifier is a separately trained RF. No rule/brand overrides or score caps.
"""
import numpy as np


class BaselineFeatureForest:
    def __init__(self, baseline, forest, input_width, baseline_width=32):
        self.baseline=baseline
        self.forest=forest
        self.classes_=forest.classes_
        self.n_features_in_=input_width
        self.baseline_width=baseline_width

    def predict_proba(self,x):
        values=np.asarray(x,dtype=np.float32)
        if values.ndim!=2 or values.shape[1]!=self.n_features_in_:
            raise ValueError('URL feature schema width mismatch')
        raw=self.baseline.predict_proba(values[:,:self.baseline_width])[:,list(self.baseline.classes_).index(1)]
        enriched=np.column_stack((values,raw)).astype(np.float32,copy=False)
        return self.forest.predict_proba(enriched)
