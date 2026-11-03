"""Evaluation Center services -- golden dataset management and batch evaluation.

Two files only (not a granular per-concern split): evaluation_dataset_service.py
owns dataset/version/question business rules, batch_eval_service.py owns batch
run orchestration. Both are thin -- they reuse the existing evaluation_dispatch.py
graph dispatch rather than reimplementing retrieval+generation+scoring.
"""
