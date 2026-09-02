"""DNS 泄露探针与回收接口单元测试。"""

import dns.message
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import DnsLeakHit
from app.services.dns_server import handle_dns_packet


def test_dns_packet_handling_and_recovery_api(tmp_path):
    db_path = tmp_path / "test_dns.db"
    test_db_url = f"sqlite:///{db_path}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # 1. 模拟 DNS 客户端发送 *.dnstest.govps.xyz 查询
    q = dns.message.make_query("testtoken0.dnstest.govps.xyz", "A")
    wire_q = q.to_wire()
    client_addr = ("1.2.3.4", 53333)

    reply_wire = handle_dns_packet(wire_q, client_addr)
    assert reply_wire is not None

    reply = dns.message.from_wire(reply_wire)
    assert len(reply.answer) > 0
    assert "43.173.89.152" in str(reply.answer[0])

    # 2. 写入数据库模拟命中记录
    with TestingSessionLocal() as db:
        hit = DnsLeakHit(
            token="testtoken",
            resolver_ip="1.2.3.4",
            query_name="testtoken0.dnstest.govps.xyz",
        )
        db.add(hit)
        db.commit()

    # 3. 调用回收接口验证
    res = client.get("/api/ip/dns-leak/results?token=testtoken")
    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is True
    assert data["token"] == "testtoken"
    assert len(data["resolvers"]) == 1
    assert data["resolvers"][0]["resolver"] == "1.2.3.4"

    # 清理 override
    app.dependency_overrides.clear()
