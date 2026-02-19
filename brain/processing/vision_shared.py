"""
Shared vision heuristics and policy utilities.

This module is framework-agnostic so web/raspi runtimes can reuse the same
engine-selection, detector field contracts, and depth/presence estimators.
"""

import re


def normalize_engine(value: str) -> str:
    v = str(value or 'auto').strip().lower()
    if v in ('vlm', 'openai', 'llm'):
        return 'vlm'
    if v in ('cv', 'opencv', 'posenet'):
        return 'cv'
    if v in ('hybrid', 'both'):
        return 'hybrid'
    return 'auto'


def looks_cv_friendly(prompt: str) -> bool:
    text = str(prompt or '').strip().lower()
    if not text:
        return True
    simple_patterns = [
        r'\bperson\b', r'\bhuman\b', r'\bface\b', r'\bbody\b', r'\bpose\b',
        r'\bhand\b', r'\bwave\b', r'\bmotion\b', r'\bmovement\b', r'\bpresence\b',
        r'\bempty room\b', r'\bcount people\b', r'\bstanding\b', r'\bsitting\b',
    ]
    complex_markers = [
        r'\bemotion\b', r'\bmood\b', r'\bintention\b', r'\bcontext\b', r'\bstory\b',
        r'\bbrand\b', r'\btext\b', r'\breading\b', r'\bproduct\b', r'\bscene\b',
        r'\bexplain\b', r'\bdescribe\b', r'\bwhy\b',
    ]
    if any(re.search(pattern, text) for pattern in complex_markers):
        return False
    return any(re.search(pattern, text) for pattern in simple_patterns)


def cv_supported_fields(detector: str) -> set:
    detector_name = str(detector or '').strip().lower()
    if detector_name in ('hog', 'opencv_hog', 'person'):
        return {'person_count'}
    if detector_name in ('face', 'opencv_face'):
        return {'face_count'}
    if detector_name in ('motion', 'opencv_motion'):
        return {'motion_score'}
    if detector_name in ('posenet', 'pose'):
        return {
            'pose_landmarks',
            'person_count',
            'pose_positions',
            'hand_positions',
            'hand_pose',
            'pose_detected',
        }
    return set()
