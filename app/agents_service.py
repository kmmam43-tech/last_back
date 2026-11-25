import asyncio
import base64
import html
import json
import os
import re

from .config import Settings
from .models import MaterialAnalysis, MaterialRequest, ReviewResult, VariantBundle, WorksheetVariant
from .prompts import ANALYSIS_INSTRUCTIONS, DIFFERENTIATION_INSTRUCTIONS, REVIEWER_INSTRUCTIONS


class LearningMaterialAgents:
    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    async def analyze(self, request: MaterialRequest) -> MaterialAnalysis:
        if not self.settings.agents_enabled:
            return self._demo_analysis(request)
        from agents import Agent, Runner

        agent = Agent(
            name="lesson-material-analysis",
            instructions=ANALYSIS_INSTRUCTIONS,
            model=self.settings.openai_model,
            output_type=MaterialAnalysis,
        )
        result = await Runner.run(agent, request.model_dump_json())
        return result.final_output

    async def generate(self, request: MaterialRequest, analysis: MaterialAnalysis) -> VariantBundle:
        if not self.settings.agents_enabled:
            bundle = self._demo_variants(request, analysis)
            self._attach_demo_image(bundle, request, analysis)
            return bundle
        from agents import Agent, Runner

        agent = Agent(
            name="differentiate-lesson-material",
            instructions=DIFFERENTIATION_INSTRUCTIONS,
            model=self.settings.openai_model,
            output_type=VariantBundle,
        )
        payload = json.dumps(
            {"request": request.model_dump(), "analysis": analysis.model_dump()},
            ensure_ascii=False,
        )
        result = await Runner.run(agent, payload)
        bundle = result.final_output
        await self._attach_generated_image(bundle, request, analysis)
        return bundle

    async def _attach_generated_image(
        self,
        bundle: VariantBundle,
        request: MaterialRequest,
        analysis: MaterialAnalysis,
    ) -> None:
        visual = next((item for item in bundle.variants if item.kind == "visual_worksheet"), None)
        if not visual:
            return
        if not visual.image_prompt:
            visual.image_prompt = f"{request.title}의 핵심 개념을 보여 주는 교육용 삽화"
        if not visual.alt_text:
            visual.alt_text = f"{request.title}의 핵심 개념을 설명하는 교육용 그림"
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.settings.openai_api_key)
            response = await client.images.generate(
                model=self.settings.openai_image_model,
                prompt=(
                    f"한국 학교 학습지에 넣을 명확한 교육용 삽화. {visual.image_prompt}. "
                    "흰 배경, 단순한 형태, 정확한 시각적 관계, 그림 안에는 글자를 넣지 않는다."
                ),
                n=1,
                size="1024x1024",
            )
            if response.data and response.data[0].b64_json:
                visual.image_data_url = f"data:image/png;base64,{response.data[0].b64_json}"
                return
        except Exception:
            # 이미지 API 실패가 전체 학습자료 생성을 막지 않도록 설명형 SVG로 대체한다.
            pass
        self._attach_demo_image(bundle, request, analysis)

    @staticmethod
    def _attach_demo_image(
        bundle: VariantBundle,
        request: MaterialRequest,
        analysis: MaterialAnalysis,
    ) -> None:
        visual = next((item for item in bundle.variants if item.kind == "visual_worksheet"), None)
        if not visual:
            return
        labels = (analysis.essential_terms + analysis.core_concepts)[:3]
        while len(labels) < 3:
            labels.append("핵심 개념")
        title = html.escape(request.title[:22])
        safe_labels = [html.escape(label[:14]) for label in labels]
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="560" viewBox="0 0 900 560">
<rect width="900" height="560" rx="28" fill="#f7fbf9"/>
<path d="M286 292h110M504 292h110" stroke="#167c71" stroke-width="8" stroke-linecap="round"/>
<path d="m380 275 24 17-24 17M598 275l24 17-24 17" fill="none" stroke="#167c71" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="190" cy="292" r="96" fill="#dbeee9" stroke="#167c71" stroke-width="5"/>
<circle cx="450" cy="292" r="96" fill="#fff3cf" stroke="#d59a2d" stroke-width="5"/>
<circle cx="710" cy="292" r="96" fill="#f7ddd6" stroke="#d9634d" stroke-width="5"/>
<text x="450" y="78" text-anchor="middle" font-family="sans-serif" font-size="38" font-weight="700" fill="#17243f">{title}</text>
<text x="190" y="302" text-anchor="middle" font-family="sans-serif" font-size="26" font-weight="700" fill="#0f5d55">{safe_labels[0]}</text>
<text x="450" y="302" text-anchor="middle" font-family="sans-serif" font-size="26" font-weight="700" fill="#74520e">{safe_labels[1]}</text>
<text x="710" y="302" text-anchor="middle" font-family="sans-serif" font-size="26" font-weight="700" fill="#843727">{safe_labels[2]}</text>
<text x="450" y="494" text-anchor="middle" font-family="sans-serif" font-size="22" fill="#53605c">핵심 개념의 관계를 순서대로 살펴보세요.</text>
</svg>'''
        visual.image_data_url = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")

    async def review_all(
        self,
        request: MaterialRequest,
        analysis: MaterialAnalysis,
        variants: VariantBundle,
    ) -> list[ReviewResult]:
        if not self.settings.agents_enabled:
            return self._demo_reviews(request, variants)
        return await asyncio.gather(
            *(self._run_reviewer(name, request, analysis, variants) for name in REVIEWER_INSTRUCTIONS)
        )

    async def _run_reviewer(self, name, request, analysis, variants) -> ReviewResult:
        from agents import Agent, Runner

        agent = Agent(
            name=name,
            instructions=REVIEWER_INSTRUCTIONS[name],
            model=self.settings.openai_model,
            output_type=ReviewResult,
        )
        payload = json.dumps(
            {
                "reviewer": name,
                "request": request.model_dump(),
                "analysis": analysis.model_dump(),
                "variants": variants.model_dump(),
            },
            ensure_ascii=False,
        )
        result = await Runner.run(agent, payload)
        output = result.final_output
        output.reviewer = name
        return output

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [item.strip() for item in re.split(r"(?<=[.!?。])\s+|\n+", text) if item.strip()]

    def _demo_analysis(self, request: MaterialRequest) -> MaterialAnalysis:
        sentences = self._sentences(request.original_text)
        terms = list(dict.fromkeys(re.findall(r"[가-힣A-Za-z]{2,}", request.original_text)))[:6]
        return MaterialAnalysis(
            learning_objectives=[sentences[0][:120] if sentences else request.title],
            core_concepts=(sentences[:3] or [request.title]),
            essential_terms=terms or [request.title],
            assessment_requirements=["핵심 개념을 자신의 말로 설명한다."],
            access_barriers=[
                "긴 문장과 한 번에 제시되는 많은 정보",
                "설명 없이 제시된 핵심 용어",
            ],
        )

    def _demo_variants(self, request: MaterialRequest, analysis: MaterialAnalysis) -> VariantBundle:
        sentences = self._sentences(request.original_text) or [request.original_text]
        easy = "\n".join(f"• {sentence[:90]}" for sentence in sentences[:6])
        terms = "\n".join(f"• {term}: 원문에서 중요한 말이에요." for term in analysis.essential_terms[:6])
        short = "\n\n".join(" ".join(sentences[i : i + 2]) for i in range(0, min(len(sentences), 6), 2))
        visual = (
            f"학습목표\n{analysis.learning_objectives[0]}\n\n"
            "살펴보기\n1. 그림의 중요한 부분을 찾습니다.\n2. 핵심어로 내용을 설명합니다.\n"
            "3. 배운 내용을 한 문장으로 정리합니다."
        )
        return VariantBundle(
            variants=[
                WorksheetVariant(kind="easy_sentences", title="쉽게 읽는 자료", content=easy),
                WorksheetVariant(kind="key_terms", title="핵심어와 함께 읽기", content=terms),
                WorksheetVariant(kind="short_paragraphs", title="짧은 단락 자료", content=short),
                WorksheetVariant(
                    kind="visual_worksheet",
                    title="그림으로 살펴보는 학습지",
                    content=visual,
                    image_prompt=f"{request.title}의 핵심 개념을 보여 주는 단순한 교육용 삽화",
                    alt_text=f"{request.title}의 핵심 개념을 단계별로 보여 주는 교육용 그림",
                ),
            ]
        )

    def _demo_reviews(self, request: MaterialRequest, variants: VariantBundle) -> list[ReviewResult]:
        has_alt = any(item.alt_text for item in variants.variants if item.kind == "visual_worksheet")
        return [
            ReviewResult(reviewer="subject_content_reviewer", passed=True, score=88, summary="원문의 핵심 흐름을 유지했습니다.", issues=[]),
            ReviewResult(reviewer="accessibility_reviewer", passed=has_alt, score=92 if has_alt else 70, summary="문장 구조와 이미지 설명을 확인했습니다.", issues=[] if has_alt else ["이미지 대체 텍스트가 필요합니다."]),
            ReviewResult(reviewer="student_perspective_reviewer", passed=True, score=86, summary=f"{request.grade} 학생이 단계별로 따라갈 수 있습니다.", issues=[]),
        ]

