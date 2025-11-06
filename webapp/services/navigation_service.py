import os
from flask import g, session, has_request_context
from webapp.extensions import cache
from webapp.navigation_builder import NavigationBuilder
from .drive_service import get_google_drive_instance

ROOT = os.getenv("ROOT_FOLDER", "library")


def reset_navigation_flags(navigation: dict) -> None:
    for _, item in navigation.items():
        item["active"] = False
        item["expanded"] = False
        if "children" in item and isinstance(item["children"], dict):
            reset_navigation_flags(item["children"])


def construct_navigation_data() -> NavigationBuilder:
    google_drive = get_google_drive_instance()
    data = NavigationBuilder(google_drive, ROOT)
    nav_data = {
        "doc_reference_dict": data.doc_reference_dict,
        "temp_hierarchy": data.temp_hierarchy,
        "file_list": data.file_list,
        "hierarchy": data.hierarchy,
    }
    cache.set("navigation", nav_data)
    if has_request_context():
        session["navigation_data_cached"] = True
    return data


def get_navigation_data() -> NavigationBuilder:
    if "navigation_data" not in g:
        if "navigation_data_cached" not in session:
            g.navigation_data = construct_navigation_data()
        else:
            nav_data = cache.get("navigation")
            if nav_data is None:
                g.navigation_data = construct_navigation_data()
            else:
                google_drive = get_google_drive_instance()
                g.navigation_data = NavigationBuilder(
                    google_drive,
                    ROOT,
                    True,
                    nav_data["doc_reference_dict"],
                    nav_data["temp_hierarchy"],
                    nav_data["file_list"],
                    nav_data["hierarchy"],
                )
    return g.navigation_data


def get_target_document(path: str, navigation: dict) -> dict:
    if not path:
        navigation["index"]["active"] = True
        return navigation["index"]

    split_slug = path.split("/")
    target_page = navigation
    for index, slug in enumerate(split_slug):
        if len(split_slug) == index + 1:
            target_page[slug]["active"] = True
            if target_page[slug]["mimeType"] == "folder":
                target_page[slug]["expanded"] = True
                return target_page[slug]["children"]["index"]
            else:
                return target_page[slug]
        target_page[slug]["expanded"] = True
        target_page = target_page[slug]["children"]

    raise ValueError(f"Document for path '{path}' not found.")
