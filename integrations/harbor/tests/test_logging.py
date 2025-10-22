from integrations.harbor.logging_utils import HarborLogContext, log_resync_summary


def test_log_context_track():
    ctx = HarborLogContext()
    ctx.track("harbor-project", updated=2)
    ctx.track("harbor-project", deleted=1)
    ctx.track("harbor-user", errors=1)

    assert ctx.updated == 2
    assert ctx.deleted == 1
    assert ctx.errors == 1
    assert ctx.by_kind["harbor-project"]["updated"] == 2
    assert ctx.by_kind["harbor-project"]["deleted"] == 1


def test_log_resync_summary_does_not_fail(caplog):
    ctx = HarborLogContext()
    ctx.track("harbor-project", updated=1)

    log_resync_summary(ctx)

    assert ctx.updated == 1


def test_log_resync_summary_includes_org_id(monkeypatch):
    ctx = HarborLogContext()
    ctx.track("harbor-project", updated=3, deleted=1)

    captured: dict[str, object] = {}

    def fake_info(message, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "integrations.harbor.logging_utils.structured.logger.info",
        fake_info,
    )

    log_resync_summary(ctx, organization_id="org-123")

    assert captured["message"] == "harbor.resync.summary"
    assert captured["kwargs"]["organization_id"] == "org-123"
