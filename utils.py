import statistics
from typing import Sequence, Union, Dict, Any, Optional

Number = Union[int, float]


def numeric_stats(data: Optional[Sequence[Number]]) -> Dict[str, Any]:
    """
    Calculate summary statistics (max, min, mean, median, samples, stdev, max_diff)
    for a sequence of numbers.

    Returns a dictionary with 'samples': 0 if the data sequence is empty or None.
    """
    if not data:
        return {"samples": 0}

    data_list = list(data)
    n = len(data_list)
    if n == 0:
        return {"samples": 0}

    stats: Dict[str, Any] = {
        "max": max(data_list),
        "min": min(data_list),
        "mean": statistics.mean(data_list),
        "median": statistics.median(data_list),
        "samples": n,
    }
    if n > 1:
        stats["stdev"] = statistics.stdev(data_list)
    stats["max_diff"] = stats["max"] - stats["min"]
    return stats

