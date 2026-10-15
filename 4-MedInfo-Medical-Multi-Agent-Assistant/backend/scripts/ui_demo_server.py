"""Local UI demo server for screenshots and UI checks - NO real models, NO quota, SYNTHETIC data only.

Runs the real app and the real safety pipeline, but with a scripted fake chat model, fake embeddings,
in-memory stores and a locally generated signing key. Pre-minted test tokens (user / clinician / admin)
are written to --tokens-out so a browser test can stub the Supabase sign-in call.

The evaluation view is seeded with numbers computed right here (offline safety suite + offline retrieval
on the synthetic golden set, fake model) - never with invented values.

Refuses to run with APP_ENV=production; binds to 127.0.0.1 only.
Usage: python scripts/ui_demo_server.py --port 8031 --tokens-out <path.json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt
import uvicorn
import yaml
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import PROJECT_ROOT, Settings
from app.container import build_container
from app.main import create_app
from app.rag.evaluation import EvalRun, GoldenSet, evidence_rank, hit_rate, mrr
from app.rag.ingest import Provenance
from app.rag.interfaces import SearchFilter
from app.rag.ocr import RapidOcrEngine
from app.safety.evaluation import SafetySuite
from tests.fakes import FakeChatModel, FakeEmbedder, StaticKeyResolver, passage_number

SUPABASE = "https://demo.invalid"
CORPUS = PROJECT_ROOT / "data" / "synthetic" / "corpus"

SCRIPTS = [  # (keyword in question, answer template, phrase that locates the passage)
    (
        "pregnan",
        'The label states "Zentoril should not be used during pregnancy" {a}. It also states "Women who become pregnant while taking Zentoril should contact their prescriber promptly" {a}.\nLIMITATIONS: Label text only; it does not cover other medicines.',
        "should not be used during pregnancy",
    ),
    (
        "double",
        'The label states "The usual starting dose of Zentoril is 10 mg once daily" {a}. It also states "Do not stop taking Zentoril suddenly without talking to your prescriber" {a}. The rest of this question is not covered by the available sources.\nLIMITATIONS: Does not cover your own dose decisions.',
        "usual starting dose",
    ),
    (
        "chest",
        "Chest pain that is crushing or spreads to the arm, jaw or back can be a sign of a heart attack and needs emergency assessment {a}. People with these symptoms should call emergency services rather than travel by themselves {a}.\nLIMITATIONS: General guidance only.",
        "heart attack",
    ),
    (
        "defined",
        "Version 3 defines hypertension as a clinic blood pressure of 140/90 mmHg or higher on repeated readings {a}. The older version 2 used 150/95 mmHg {b}. Hypertension often causes no symptoms, so regular measurement is the main way it is found {a}.\nLIMITATIONS: Does not cover treatment choices.",
        ("140/90 mmHg or higher on repeated", "150/95"),
    ),
    (
        "hypertension",
        "Hypertension means blood pressure that stays raised over time {a}. In the current guideline it is defined as a clinic blood pressure of 140/90 mmHg or higher on repeated readings {a}. Hypertension often causes no symptoms, so regular measurement is the main way it is found {a}.\nLIMITATIONS: Does not cover causes or treatment.",
        "140/90 mmHg or higher on repeated",
    ),
    (
        "thirst",
        "Common symptoms of type 2 diabetes include feeling very thirsty, passing urine more often, tiredness and blurred vision {a}. Diabetes is confirmed by blood tests such as HbA1c; symptoms alone cannot confirm it {a}.\nLIMITATIONS: General information only.",
        "feeling very thirsty",
    ),
]


def demo_answer(system: str, user: str) -> str:
    q = user.split("<question>", 1)[-1].lower()
    for key, template, phrase in SCRIPTS:
        if key in q:
            try:
                if isinstance(phrase, tuple):
                    return template.format(
                        a=f"[{passage_number(user, phrase[0])}]", b=f"[{passage_number(user, phrase[1])}]"
                    )
                return template.format(a=f"[{passage_number(user, phrase)}]")
            except AssertionError:
                return "NOT_COVERED"
    return "NOT_COVERED"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8031)
    ap.add_argument("--tokens-out", required=True)
    args = ap.parse_args()
    if os.environ.get("APP_ENV") == "production":
        sys.exit("refusing to run the demo server in production")

    key = ec.generate_private_key(ec.SECP256R1())
    settings = Settings(
        _env_file=None,
        app_env="local",
        supabase_url=SUPABASE,
        supabase_publishable_key="demo",
        retrieval_backend="memory",
        retrieval_min_similarity=0.0,
        review_sample_rate=1.0,
        emergency_number="112",
        crisis_line_name="Demo Crisis Line",
        crisis_line_number="0000 DEMO",
        rate_limit_chat_per_minute=1000,
        log_level="WARNING",
    )
    model = FakeChatModel(answer=demo_answer, scope=None)
    container = build_container(
        settings,
        model=model,
        classifier=model,
        embedder=FakeEmbedder(dimensions=256),
        ocr=RapidOcrEngine(),
        key_resolver=StaticKeyResolver(key.public_key()),
    )
    manifest = yaml.safe_load((CORPUS / "manifest.yaml").read_text(encoding="utf-8"))["documents"]
    for name, meta in manifest.items():
        container.ingest.ingest_trusted(
            name, (CORPUS / name).read_bytes(), Provenance(**meta), actor_id="demo"
        )

    # Seed the evaluation view with numbers computed here (fake model, synthetic set).
    golden = GoldenSet.load(PROJECT_ROOT / "evals" / "golden.yaml")
    ranks = [
        evidence_rank(
            i.evidence, container.retriever.retrieve(i.question, 5, SearchFilter(trusted_only=True))
        )
        for i in golden.items
    ]
    suite = SafetySuite.load(
        PROJECT_ROOT / "evals" / "safety_suite.yaml", PROJECT_ROOT / "data" / "synthetic" / "uploads"
    )
    report = suite.run(
        container.chat,
        ingest=container.ingest,
        out_of_corpus=list(golden.out_of_corpus),
        sent_prompts=lambda: model.prompts,
    )
    metrics = {
        "retrieval_evidence_hit_rate": hit_rate(ranks, 5),
        "retrieval_mrr": mrr(ranks),
        **{f"safety_{k}": v for k, v in report.rates.items()},
    }
    container.eval_runs.add(
        EvalRun(
            uuid.uuid4().hex,
            time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            "offline evaluation on a synthetic test set (demo, fake model)",
            {"answer_model": "fake (demo)", "items": len(golden.items)},
            metrics,
        )
    )
    for item in container.review.queue(1000):  # suite answers are not review material for the demo
        container.review.record(item.id, verdict="safe_and_correct", notes="demo", reviewer_id="demo")

    def mint(role: str, sub: str, email: str) -> str:
        claims = {
            "sub": sub,
            "email": email,
            "aud": "authenticated",
            "iss": f"{SUPABASE}/auth/v1",
            "exp": int(time.time()) + 6 * 3600,
            "role": "authenticated",
            "app_metadata": {"role": role},
        }
        return jwt.encode(claims, key, algorithm="ES256")

    tokens = {r: mint(r, f"demo-{r}", f"{r}@example.test") for r in ("user", "clinician", "admin")}
    Path(args.tokens_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.tokens_out).write_text(
        json.dumps({"supabase_url": SUPABASE, "tokens": tokens}), encoding="utf-8"
    )
    print(f"demo ready on http://127.0.0.1:{args.port}  metrics={json.dumps(metrics)}", flush=True)
    uvicorn.run(create_app(container), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
