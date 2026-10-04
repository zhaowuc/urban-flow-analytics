from backend.app.services.demo_data import generate_records, load_catalog, validate_catalog, validate_records


def test_fixed_city_catalog_counts_and_route_integrity():
    catalog = load_catalog()
    validate_catalog(catalog)
    assert len(catalog["regions"]) == 8
    assert len(catalog["stations"]) == 40
    assert len(catalog["routes"]) == 12


def test_generated_records_share_the_fixed_catalog():
    frame = generate_records(500, seed=20260827)
    validate_records(frame)
    assert (frame["origin_station"] != frame["destination_station"]).all()
    assert set(frame["transport_type"]) == {"bus", "metro", "taxi", "ride_hailing", "bike"}

