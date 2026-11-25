import inspect

from agents import Agent, Runner
from pydantic import ValidationError

from app.agents_service import LearningMaterialAgents
from app.config import Settings
from app.models import MaterialRequest
from app.workflow import build_workflow


SAMPLE_TEXT = "물은 온도에 따라 상태가 변합니다. 얼음은 고체이고 물은 액체입니다. 수증기는 기체입니다."


def make_request():
    return MaterialRequest(
        title="물의 상태 변화",
        author="김교사",
        grade="초등 4학년",
        language_level="쉬운 한국어",
        supports=["짧은 문장", "이미지 설명"],
        original_text=SAMPLE_TEXT,
    )


def test_demo_generation_contract():
    service = LearningMaterialAgents(Settings(openai_api_key="", openai_model=""))
    request = make_request()
    analysis = service._demo_analysis(request)
    variants = service._demo_variants(request, analysis)
    service._attach_demo_image(variants, request, analysis)
    reviews = service._demo_reviews(request, variants)

    assert analysis.learning_objectives
    assert {variant.kind for variant in variants.variants} == {
        "easy_sentences",
        "key_terms",
        "short_paragraphs",
        "visual_worksheet",
    }
    visual = next(item for item in variants.variants if item.kind == "visual_worksheet")
    assert visual.alt_text
    assert visual.image_data_url.startswith("data:image/svg+xml;base64,")
    assert {review.reviewer for review in reviews} == {
        "subject_content_reviewer",
        "accessibility_reviewer",
        "student_perspective_reviewer",
    }


def test_short_source_is_rejected():
    try:
        MaterialRequest(
            title="짧은 자료",
            grade="초등 3학년",
            language_level="기본",
            original_text="너무 짧음",
        )
    except ValidationError:
        return
    raise AssertionError("짧은 원문이 거부되어야 합니다.")


def test_agents_sdk_and_langgraph_are_wired():
    assert Agent is not None
    assert inspect.iscoroutinefunction(Runner.run)
    workflow = build_workflow(LearningMaterialAgents(Settings(openai_api_key="", openai_model="")))
    assert {"analyze", "differentiate", "review"}.issubset(workflow.nodes)
