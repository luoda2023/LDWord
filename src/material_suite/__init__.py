"""Package-driven multi-artifact suite generation."""

from .plan import (
    GenerationRecipe,
    MaterialSuiteRunPlan,
    MaterialSuiteRunRequest,
    PackageInspection,
    PackageRecordInspection,
    SuiteArtifactPlan,
    SuiteArtifactSpec,
    SuiteRecordPlan,
    SuiteTemplateBundle,
    compile_material_suite_plan,
    discover_material_suite_bundle,
)
from .runner import MaterialSuiteGenerationRunner

__all__ = [
    "MaterialSuiteGenerationRunner",
    "GenerationRecipe",
    "MaterialSuiteRunPlan",
    "MaterialSuiteRunRequest",
    "PackageInspection",
    "PackageRecordInspection",
    "SuiteArtifactPlan",
    "SuiteArtifactSpec",
    "SuiteRecordPlan",
    "SuiteTemplateBundle",
    "compile_material_suite_plan",
    "discover_material_suite_bundle",
]
