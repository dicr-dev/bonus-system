from collections.abc import Iterable

from cr_portal.models.user import User

KPI_DEPARTMENT_IDS = {
    "20": "Отдел внедрения",
    "33": "Разработка 1С",
}
KPI_DEPARTMENT_NAMES = frozenset(KPI_DEPARTMENT_IDS.values())


def kpi_department_name_from_user_data(data: dict) -> str | None:
    department_ids = data.get("UF_DEPARTMENT") or data.get("ufDepartment") or []
    if not isinstance(department_ids, list):
        department_ids = [department_ids]
    names = list(
        dict.fromkeys(
            KPI_DEPARTMENT_IDS[str(department_id)]
            for department_id in department_ids
            if str(department_id) in KPI_DEPARTMENT_IDS
        )
    )
    return "; ".join(names) or None


def employee_is_in_department(user: User | None, department_name: str) -> bool:
    if user is None or not user.department_name:
        return False
    departments = {
        value.strip()
        for value in user.department_name.split(";")
        if value.strip()
    }
    return department_name in departments


def employee_is_in_kpi_department(user: User | None) -> bool:
    return any(
        employee_is_in_department(user, department_name)
        for department_name in KPI_DEPARTMENT_NAMES
    )


def eligible_bonus_users(users: Iterable[User]) -> list[User]:
    return [
        user
        for user in users
        if user.is_active and employee_is_in_kpi_department(user)
    ]
