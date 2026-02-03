"""Connaissances spécialisées sur les frameworks Python pour éviter les faux positifs."""

FRAMEWORK_RULES = {
    "django": {
        "classes_vivantes": {"Meta", "Config", "DoesNotExist", "MultipleObjectsReturned"},
        "methodes_vivantes": {
            "save", "delete", "clean", "full_clean", "get_absolute_url", 
            "get_context_data", "get_queryset", "handle", "ready", "dispatch"
        },
        "decorateurs_racines": {"receiver"},
        "parents_vivants": {"Model", "View", "Form", "Serializer", "Task"}
    },
    "fastapi_flask": {
        "decorateurs_racines": {
            "get", "post", "put", "delete", "patch", "route", "on_event", "exception_handler",
            "app.get", "app.post", "router.get", "router.post"
        },
        "dependances": {"Depends", "Body", "Query", "Path", "Header", "Cookie", "File", "Form"}
    },
    "pytest": {
        "decorateurs_racines": {"fixture", "pytest.fixture", "parametrize", "mark"},
        "prefixes_fonctions": {"test_", "pytest_"},
        "fichiers_speciaux": {"conftest.py"}
    },
    "pydantic": {
        "classes_vivantes": {"Config", "SettingsConfigDict"},
        "decorateurs_vivants": {"validator", "field_validator", "model_validator", "computed_field"}
    }
}