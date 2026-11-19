"""Nest COMPONENT/RELATED children and assemble category / subcategory blocks."""

from collections import defaultdict
from typing import NamedTuple, TypedDict

from data_visualization.services.config import ECONOMIC_SUBCATEGORIES_BY_CATEGORY
from data_visualization.services.economic_recap.table_content import (
    EconomicRecapItem,
    RecapLineKey,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataSubcategoryChoices,
    IndicatorExpansionRelationChoices,
)

_PCT_OF_GDP_SUFFIX = " (% of GDP)"


class EconomicRecapSubcategoryGroup(TypedDict):
    """One subcategory block in the economic recap table (ordered payload)."""

    subcategory: EconomicDataSubcategoryChoices
    # Distinct indicator names in this subcategory (rowspan for the subcategory cell).
    indicator_row_count: int
    # Named 'entries' (not 'items') so Django templates do not resolve 'dict.items'.
    entries: list[EconomicRecapItem]


class EconomicRecapCategoryGroup(TypedDict):
    """One category block in the economic recap table (ordered payload)."""

    category: EconomicDataCategoryChoices
    # Distinct indicator names across subcategories (rowspan for the category cell).
    indicator_row_count: int
    subcategories: list[EconomicRecapSubcategoryGroup]


class _RecapSubcategoryLineIndex(NamedTuple):
    """Per-line recap cells and expansion metadata for one subcategory block."""

    # Usage of dict: keys are distinct line names in this subcategory.
    items_by_line_name: dict[str, list[EconomicRecapItem]]
    parent_series_label_by_line_name: dict[str, str]
    expansion_relation_by_line_name: dict[str, str]
    line_order: list[str]


def _index_recap_subcategory_lines(
    subcategory_line_items: list[tuple[RecapLineKey, list[EconomicRecapItem]]],
) -> _RecapSubcategoryLineIndex:
    """Collect line names, parent links, and cells for one subcategory block."""
    items_by_line_name: dict[str, list[EconomicRecapItem]] = {}
    parent_series_label_by_line_name: dict[str, str] = {}
    expansion_relation_by_line_name: dict[str, str] = {}
    line_order: list[str] = []
    for recap_line_key, recap_items in subcategory_line_items:
        line_name = recap_line_key.line_name
        items_by_line_name[line_name] = recap_items
        # Every recap line shares one parent label and expansion relation from
        # its first cell.
        parent_series_label_by_line_name[line_name] = recap_items[0][
            "parent_series_label"
        ]
        expansion_relation_by_line_name[line_name] = str(
            recap_items[0]["expansion_relation"] or ""
        )
        line_order.append(line_name)
    return _RecapSubcategoryLineIndex(
        items_by_line_name=items_by_line_name,
        parent_series_label_by_line_name=parent_series_label_by_line_name,
        expansion_relation_by_line_name=expansion_relation_by_line_name,
        line_order=line_order,
    )


class _NestedAndTopLevelLineNames(NamedTuple):
    """COMPONENT children keyed by parent, plus top-level line names."""

    # Usage of dict: parent series label → nested child line names.
    children_by_parent: dict[str, list[str]]
    top_level_line_names: list[str]


def _split_nested_and_top_level_line_names(
    line_index: _RecapSubcategoryLineIndex,
) -> _NestedAndTopLevelLineNames:
    """Return COMPONENT children keyed by parent and top-level line names."""
    # Usage of dict: parent series label → nested child line names.
    children_by_parent: dict[str, list[str]] = defaultdict(list)
    top_level_line_names: list[str] = []
    for line_name in line_index.line_order:
        parent_series_label = line_index.parent_series_label_by_line_name[line_name]
        expansion_relation = line_index.expansion_relation_by_line_name[line_name]
        is_nested_child = (
            expansion_relation
            in {
                IndicatorExpansionRelationChoices.COMPONENT,
                IndicatorExpansionRelationChoices.RELATED,
            }
            and bool(parent_series_label)
            and parent_series_label in line_index.items_by_line_name
        )
        if is_nested_child:
            children_by_parent[parent_series_label].append(line_name)
            continue
        if parent_series_label:
            # Orphaned parent links become independent top-level indicators.
            for recap_item in line_index.items_by_line_name[line_name]:
                recap_item["parent_series_label"] = ""
                recap_item["expansion_relation"] = ""
        top_level_line_names.append(line_name)
    return _NestedAndTopLevelLineNames(
        children_by_parent=children_by_parent,
        top_level_line_names=top_level_line_names,
    )


def _sort_top_level_lines_with_pct_gdp_pairs(
    top_level_line_names: list[str],
) -> list[str]:
    """Keep each '% of GDP' twin immediately under its outstanding parent line.

    Example: Current Account, then Current Account (% of GDP), then other
    top-level TRADE lines. Discovery order is preserved otherwise.
    """
    top_level_set = set(top_level_line_names)
    sorted_top_level_line_names: list[str] = []
    already_placed: set[str] = set()
    for line_name in top_level_line_names:
        if line_name in already_placed:
            continue
        if line_name.endswith(_PCT_OF_GDP_SUFFIX):
            outstanding_line_name = line_name[: -len(_PCT_OF_GDP_SUFFIX)]
            if (
                outstanding_line_name in top_level_set
                and outstanding_line_name not in already_placed
            ):
                sorted_top_level_line_names.append(outstanding_line_name)
                already_placed.add(outstanding_line_name)
            sorted_top_level_line_names.append(line_name)
            already_placed.add(line_name)
            continue
        sorted_top_level_line_names.append(line_name)
        already_placed.add(line_name)
        pct_of_gdp_line_name = f"{line_name}{_PCT_OF_GDP_SUFFIX}"
        if (
            pct_of_gdp_line_name in top_level_set
            and pct_of_gdp_line_name not in already_placed
        ):
            sorted_top_level_line_names.append(pct_of_gdp_line_name)
            already_placed.add(pct_of_gdp_line_name)
    return sorted_top_level_line_names


def _list_sorted_recap_items_depth_first(
    top_level_line_names: list[str],
    *,
    items_by_line_name: dict[str, list[EconomicRecapItem]],
    children_by_parent: dict[str, list[str]],
) -> list[EconomicRecapItem]:
    """Flatten parent lines and nested COMPONENT descendants in display order."""

    def _append_line_and_descendants(line_name: str) -> None:
        """Append one line then its COMPONENT descendants depth-first."""
        sorted_recap_items.extend(items_by_line_name[line_name])
        for child_line_name in children_by_parent.get(line_name, []):
            _append_line_and_descendants(child_line_name)

    sorted_recap_items: list[EconomicRecapItem] = []
    for line_name in top_level_line_names:
        _append_line_and_descendants(line_name)
    return sorted_recap_items


def _sort_nested_recap_items_for_subcategory(
    subcategory_line_items: list[tuple[RecapLineKey, list[EconomicRecapItem]]],
) -> list[EconomicRecapItem]:
    """Nest COMPONENT and RELATED children under their parent.

    'COMPONENT' indicators stay collapsed under a parent (Raw / Rel / Contr share
    math). 'RELATED' indicators also nest for drill-down, but the UI does not treat
    them as additive shares of the parent. Orphaned parent links (parent series
    label missing from this subcategory) become independent top-level indicators.
    """
    line_index = _index_recap_subcategory_lines(subcategory_line_items)
    children_by_parent, top_level_line_names = _split_nested_and_top_level_line_names(
        line_index
    )
    top_level_line_names = _sort_top_level_lines_with_pct_gdp_pairs(
        top_level_line_names
    )
    return _list_sorted_recap_items_depth_first(
        top_level_line_names,
        items_by_line_name=line_index.items_by_line_name,
        children_by_parent=children_by_parent,
    )


def _count_top_level_recap_indicators(recap_items: list[EconomicRecapItem]) -> int:
    """Count visible parent indicators for category / subcategory table rowspans."""
    return len(
        {
            recap_item["name"]
            for recap_item in recap_items
            if not recap_item["parent_series_label"]
        }
    )


def _get_recap_subcategory_group(
    category: EconomicDataCategoryChoices,
    subcategory: EconomicDataSubcategoryChoices,
    recap_lines_by_key: list[tuple[RecapLineKey, list[EconomicRecapItem]]],
) -> EconomicRecapSubcategoryGroup | None:
    """Return one subcategory block in catalog id order, or None when empty."""
    subcategory_line_items = [
        (recap_line_key, recap_items)
        for recap_line_key, recap_items in recap_lines_by_key
        if recap_line_key.category == category
        and recap_line_key.subcategory == subcategory
    ]
    if not subcategory_line_items:
        return None
    sorted_recap_items = _sort_nested_recap_items_for_subcategory(
        subcategory_line_items
    )
    return EconomicRecapSubcategoryGroup(
        subcategory=subcategory,
        indicator_row_count=_count_top_level_recap_indicators(sorted_recap_items),
        entries=sorted_recap_items,
    )


def list_economic_recap_category_groups(
    recap_lines_by_key: list[tuple[RecapLineKey, list[EconomicRecapItem]]],
) -> list[EconomicRecapCategoryGroup]:
    """Assemble category blocks in config order from built recap lines."""
    economic_data_by_category: list[EconomicRecapCategoryGroup] = []
    for category in EconomicDataCategoryChoices.ordered():
        subcategory_groups: list[EconomicRecapSubcategoryGroup] = []
        category_top_level_row_count = 0
        for subcategory in ECONOMIC_SUBCATEGORIES_BY_CATEGORY[category]:
            subcategory_group = _get_recap_subcategory_group(
                category,
                subcategory,
                recap_lines_by_key,
            )
            if subcategory_group is None:
                continue
            category_top_level_row_count += subcategory_group["indicator_row_count"]
            subcategory_groups.append(subcategory_group)
        if subcategory_groups:
            economic_data_by_category.append(
                EconomicRecapCategoryGroup(
                    category=category,
                    indicator_row_count=category_top_level_row_count,
                    subcategories=subcategory_groups,
                )
            )
    return economic_data_by_category
