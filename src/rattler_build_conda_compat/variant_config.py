from __future__ import annotations

from itertools import product


def variant_combinations(data: dict[str, list[str]]) -> list[dict[str, str]]:
    """
    This function takes a "variant" configuration dictionary that gets expanded into multiple build matrices.

    Arguments:
    ----------
    * `data` - A dictionary with keys as the variant names and values as the possible values.
    * `zip_keys` - A list of lists of keys that should be zipped together.

    Returns:
    --------
    A list of dictionaries that represent the different combinations of the variant configuration
    """
    zip_keys = data.pop("zip_keys", [])
    # Separate the keys that need to be zipped from the rest
    zip_keys_flat = [item for sublist in zip_keys for item in sublist]
    other_keys = [key for key in data if key not in zip_keys_flat]

    # Create combinations for non-zipped keys
    other_combinations = list(product(*[data[key] for key in other_keys]))

    # Create zipped combinations
    zipped_combinations = [
        list(zip(*[data[key] for key in zip_group], strict=False)) for zip_group in zip_keys
    ]

    # Combine zipped combinations
    zipped_product = list(product(*zipped_combinations))

    # Combine all results into dictionaries
    final_combinations = []
    for other_combo in other_combinations:
        for zipped_combo in zipped_product:
            combined = {}
            # Add non-zipped items
            for key, value in zip(other_keys, other_combo, strict=False):
                combined[key] = str(value)
            # Add zipped items
            for zip_group, zip_values in zip(zip_keys, zipped_combo, strict=False):
                for key, value in zip(zip_group, zip_values, strict=False):
                    combined[key] = str(value)
            final_combinations.append(combined)

    return final_combinations
