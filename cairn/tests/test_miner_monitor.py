from cairn.server import miner_monitor


def test_parse_summary():
    result = miner_monitor.parse_summary(
        "NAME=cpuminer-opt 26.1|ALGO=yescrypt|"
        "CPUS=8|KHS=0.54|ACC=1417|REJ=0|TEMP=42|UPTIME=43944"
    )

    assert result["name"] == "cpuminer-opt 26.1"
    assert result["algorithm"] == "yescrypt"
    assert result["cpus"] == 8
    assert result["khs"] == 0.54
    assert result["accepted"] == 1417
    assert result["rejected"] == 0
    assert result["temperature"] == 42


def test_parse_summary_rejects_invalid_data():
    try:
        miner_monitor.parse_summary("not a summary")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid summary should be rejected")


def test_get_miners_uses_configured_hosts(monkeypatch):
    monkeypatch.setenv("CAIRN_MINER_IPS", "10.0.0.1,10.0.0.2,10.0.0.3")
    monkeypatch.setattr(miner_monitor, "MINER_IPS", miner_monitor._miner_ips())
    calls = []

    def fake_read(ip):
        calls.append(ip)
        return {"ip": ip, "status": "online"}

    monkeypatch.setattr(miner_monitor, "_read_one", fake_read)
    result = miner_monitor.get_miners()

    assert result["total"] == len(miner_monitor.MINER_IPS)
    assert result["online"] == len(miner_monitor.MINER_IPS)
    assert result["offline"] == 0
    assert set(calls) == set(miner_monitor.MINER_IPS)


def test_get_miners_counts_offline(monkeypatch):
    monkeypatch.setenv(
        "CAIRN_MINER_IPS",
        "10.0.0.1,10.0.0.2,10.0.0.3,10.0.0.4,10.0.0.5,"
        "10.0.0.6,10.0.0.7,10.0.0.8,10.0.0.104",
    )
    monkeypatch.setattr(miner_monitor, "MINER_IPS", miner_monitor._miner_ips())

    def fake_read(ip):
        status = "offline" if ip.endswith(".104") else "online"
        return {"ip": ip, "status": status}

    monkeypatch.setattr(miner_monitor, "_read_one", fake_read)
    result = miner_monitor.get_miners()

    assert result["total"] == 9
    assert result["online"] == 8
    assert result["offline"] == 1


def test_parse_semicolon_summary():
    result = miner_monitor.parse_summary(
        "NAME=cpuminer-opt;VER=26.1;ALGO=yescrypt;"
        "CPUS=8;KHS=0.53;ACC=1455;REJ=0;TEMP=42;UPTIME=45203"
    )

    assert result["name"] == "cpuminer-opt"
    assert result["algorithm"] == "yescrypt"
    assert result["cpus"] == 8
    assert result["khs"] == 0.53
    assert result["accepted"] == 1455
    assert result["rejected"] == 0
    assert result["temperature"] == 42
    assert result["uptime"] == 45203
