import statistics


def numeric_stats(data):
    stats = {
        "max": max(data),
        "min": min(data),
        "mean": statistics.mean(data),
        "median": statistics.median(data),

        "samples": len(data)
    }
    if stats["samples"] > 1:
        stats["stdev"] = statistics.stdev(data)
    stats["max_diff"] = stats["max"] - stats["min"]
    return stats
