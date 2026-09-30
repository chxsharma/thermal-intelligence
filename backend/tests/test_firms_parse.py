from app.providers.live import parse_firms_csv


def test_parse_validates_required_columns():
    try:
        parse_firms_csv("foo,bar\n1,2")
        assert False, "should fail"
    except ValueError as exc:
        assert "latitude" in str(exc)


def test_parse_firms_rows():
    csv = """latitude,longitude,acq_date,acq_time,frp,confidence,bright_ti4,daynight,satellite,instrument
22.37,69.86,2026-09-01,1812,12.5,n,340.1,N,NOAA-20,VIIRS
"""
    rows = parse_firms_csv(csv)
    assert len(rows) == 1
    assert rows[0].frp == 12.5
    assert rows[0].day_night == "N"
