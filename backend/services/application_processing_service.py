from backend.services.application_service import get_application
from backend.services.requirement_extractor import (
    extract_application_requirements,
)
from backend.services.eligibility_engine import (
    analyze_application_eligibility,
)
from backend.services.deficiency_detector import (
    detect_application_deficiencies,
)
from backend.services.ai_analysis_service import (
    generate_application_analysis,
)


def process_application(application_id):
    """
    Run the complete AI-assisted application processing pipeline.

    Processing order:
    1. Extract applicable ordinance requirements
    2. Analyze eligibility against those requirements
    3. Detect potential deficiencies
    4. Generate an AI-assisted application analysis

    This service only orchestrates existing services.
    It does not make or record a final academic decision.
    Final approval or rejection must be made by authorized
    officials or the appropriate committee.
    """

    # ---------------------------------------------------------
    # 0. Verify application exists
    # ---------------------------------------------------------
    application = get_application(application_id)

    if application is None:
        raise ValueError(
            f"Application with id {application_id} does not exist."
        )

    # ---------------------------------------------------------
    # 1. Extract application requirements
    # ---------------------------------------------------------
    requirements_result = extract_application_requirements(
        application_id
    )

    # ---------------------------------------------------------
    # 2. Analyze eligibility
    # ---------------------------------------------------------
    eligibility_result = analyze_application_eligibility(
        application_id
    )

    # ---------------------------------------------------------
    # 3. Detect deficiencies
    # ---------------------------------------------------------
    deficiency_result = detect_application_deficiencies(
        application_id
    )

    # ---------------------------------------------------------
    # 4. Generate AI-assisted application analysis
    # ---------------------------------------------------------
    analysis_result = generate_application_analysis(
        application_id
    )

    # ---------------------------------------------------------
    # 5. Return complete processing result
    # ---------------------------------------------------------
    return {
        "application_id": application_id,
        "requirements": requirements_result,
        "eligibility": eligibility_result,
        "deficiencies": deficiency_result,
        "ai_analysis": analysis_result,
    }
