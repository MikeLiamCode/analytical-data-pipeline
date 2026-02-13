from __future__ import annotations

import pandas as pd

from keye.analysis.concentration import _concentration_for_period


def test_concentration_bucket_counts_and_sums():
    df = pd.DataFrame(
        {
            "group_by": ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],
            "value": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        }
    )
    res = _concentration_for_period(df, (0.1, 0.2, 0.5))
    assert res["top_10"]["count"] == 1
    assert res["top_10"]["sum"] == 10
    assert res["top_20"]["count"] == 2
    assert res["top_20"]["sum"] == 19
    assert res["top_50"]["count"] == 5
    assert res["top_50"]["sum"] == 40
    assert res["total"]["count"] == 10
    assert res["total"]["sum"] == 55
