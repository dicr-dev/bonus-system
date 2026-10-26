from io import BytesIO

from openpyxl import Workbook

from cr_portal.services.fuel_cards import binding_key, preview, selected_bindings


def xlsx(headers, rows):
    book = Workbook()
    sheet = book.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    data = BytesIO()
    book.save(data)
    return data.getvalue()


def test_preview_reads_multiple_card_brands_from_one_row():
    imported = xlsx(
        ["Госномер", "ID", "ТАИФ", "Делкойл", "Газпромнефть", "Роснефть"],
        [["В 011 НА/06", 22596805, "001", "002", "003", "004"]],
    )

    result = preview(imported)

    assert result["ready"] == 4
    assert {item["brand"] for item in result["items"]} == {"Tatneft", "Azimuth", "Gazpromneft", "Rosneft"}
    assert {item["car_id"] for item in result["items"]} == {22596805}


def test_preview_accepts_formatted_real_world_headers():
    imported = xlsx(["Гос. номер", "ID ТС", "Номер карты ТАИФ (Tatneft)"], [["А001АА01", 1, "001"]])

    result = preview(imported)

    assert result["ready"] == 1
    assert result["items"][0]["brand"] == "Tatneft"


def test_preview_finds_headers_after_report_title():
    imported = xlsx(
        ["Выгрузка топливных карт", None, None, None],
        [["Дата", None, None, None], ["Регистрационный номер", "ID машины", "Роснефть", None], ["А001АА01", 1, "001", None]],
    )

    result = preview(imported)

    assert result["ready"] == 1
    assert result["items"][0]["car_id"] == 1


def test_preview_accepts_number_as_plate_header_for_fuel_card_import():
    imported = xlsx(["Номер", "ID", "ТАИФ"], [["А001АА01", 1, "001"]])

    result = preview(imported)

    assert result["ready"] == 1
    assert result["items"][0]["plate"] == "А001АА01"


def test_preview_marks_duplicate_card_in_brand_columns():
    imported = xlsx(["госномер", "id", "ТАИФ", "Роснефть"], [["А001АА01", 1, "1", "1"]])

    result = preview(imported)

    assert result["ready"] == 1
    assert result["errors"] == 1
    assert "Повторяющийся" in result["items"][1]["error"]


def test_selected_bindings_limits_apply_batch_to_selected_cards():
    imported = xlsx(["госномер", "id", "ТАИФ", "Роснефть"], [["А001АА01", 1, "1", "2"]])
    result = preview(imported)

    selected = selected_bindings(result["items"], {binding_key(result["items"][0])})

    assert len(selected) == 1
    assert selected[0]["number"] == "1"
