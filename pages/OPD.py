"""
OPD Consultation Dashboard
============================
Out Patient Department — Doctor consultation flow.
Patients come here after registration for doctor checkup.
"""
from pages._department_base import show_department


def show():
    show_department("OPD", "🩺")
