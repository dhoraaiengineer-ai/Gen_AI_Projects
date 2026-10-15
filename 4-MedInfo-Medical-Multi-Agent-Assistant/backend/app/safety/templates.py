"""Fixed safety wording. These texts are assembled in code, never written by the LLM, so the model
cannot soften, reword or drop them."""

from __future__ import annotations

from dataclasses import dataclass

DISCLAIMER = "This is general information, not medical advice. Consult a qualified healthcare professional."
MEDICINE_CHANGE_WARNING = "Talk to your doctor or pharmacist before changing any medicine."
NOT_COVERED = (
    "This question is not covered by the available sources, so I can't answer it. "
    "I only answer from the trusted documents I have, never from general model knowledge. "
    "A doctor, pharmacist or other qualified professional can help."
)
DEFAULT_LIMITATIONS = (
    "Based only on the retrieved passages; it does not cover your personal medical history, "
    "other conditions or medicines, and may not reflect the newest guidance."
)


@dataclass(frozen=True)
class SafetyContacts:
    emergency_number: str
    emergency_service_name: str = "emergency services"
    crisis_line_name: str = ""
    crisis_line_number: str = ""
    poison_line_number: str = ""

    def crisis_line(self) -> str:
        if self.crisis_line_number:
            name = self.crisis_line_name or "a crisis line"
            return f"{name} on {self.crisis_line_number}"
        return "your local crisis line"


def emergency_message(contacts: SafetyContacts) -> str:
    return (
        f"This may be a medical emergency. Call {contacts.emergency_number} "
        f"({contacts.emergency_service_name}) or go to the nearest emergency department now. "
        "Seek emergency care now - do not wait for an online answer."
    )


def crisis_message(contacts: SafetyContacts) -> str:
    return (
        "If you are thinking about suicide or harming yourself, you are not alone and help is available "
        f"right now. Please contact {contacts.crisis_line()}, or call {contacts.emergency_number} if you "
        "are in immediate danger. If you can, tell someone you trust and stay with them."
    )


def poison_message(contacts: SafetyContacts) -> str | None:
    if not contacts.poison_line_number:
        return None
    return f"For poisoning or overdose advice, call the poison information line on {contacts.poison_line_number}."


def diagnosis_referral() -> str:
    return (
        "I can't tell you whether you have a particular condition - only a clinician who can assess you "
        "can do that. Below is general information from trusted sources; please see a doctor or other "
        "qualified healthcare professional about your symptoms."
    )


def prescribing_refusal() -> str:
    return (
        "I can't recommend a medicine, choose a dose, or advise starting, stopping or changing a dose. "
        "Those decisions depend on your health, other medicines and history, and must be made with your "
        f"doctor or pharmacist. {MEDICINE_CHANGE_WARNING}"
    )


def prescribing_cite_only_intro() -> str:
    return (
        "I can't advise you on what to take or how to change a dose. Here is what the source documents "
        "say, quoted exactly:"
    )


def out_of_scope_redirect() -> str:
    return (
        "I'm a medical information assistant, so I can only help with health and medical questions "
        "answered from trusted sources. Please ask a health-related question."
    )


def unsafe_refusal(contacts: SafetyContacts) -> str:
    return (
        "I can't help with that request because it could cause serious harm. "
        f"If you or someone else is at risk, please contact {contacts.crisis_line()} or call "
        f"{contacts.emergency_number}. If you are struggling with substance use, a doctor or local support "
        "service can help confidentially."
    )


def injection_refusal() -> str:
    return (
        "I can't follow instructions that try to change how I work or remove my safety checks. "
        "Please ask a medical information question and I'll answer it from trusted sources."
    )


def too_long() -> str:
    return "That message is too long for me to check safely. Please shorten it and ask again."


def blocked_answer() -> str:
    return (
        "I couldn't produce an answer that I could fully verify against the sources, so I'm not showing "
        "it. Please rephrase your question, or ask a doctor or pharmacist."
    )


def staleness_note(titles: list[str], years: int) -> str:
    return (
        f"Some cited sources are more than {years} years old and may be out of date: "
        + "; ".join(titles)
        + "."
    )
