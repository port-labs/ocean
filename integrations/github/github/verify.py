def verify_webhook_configuration():
    """Verify that webhook configuration is correct for issues."""

    print("🔍 Verifying GitHub Integration Webhook Configuration...")

    # Check repository events
    from github.webhook.events import RepositoryEvents, OrganizationEvents

    repo_events = RepositoryEvents()
    org_events = OrganizationEvents()

    repo_dict = repo_events.to_dict()
    org_dict = org_events.to_dict()

    print(f"\n📋 Repository Events: {repo_dict}")
    print(f"📋 Organization Events: {org_dict}")

    # Verify issues are in repository events
    if repo_dict.get("issues") is True:
        print("✅ Issues are enabled for repository webhooks")
    else:
        print("❌ Issues are NOT enabled for repository webhooks")

    # Verify issues are NOT in organization events
    if "issues" not in org_dict:
        print("✅ Issues are correctly excluded from organization webhooks")
    else:
        print("❌ Issues are incorrectly included in organization webhooks")

    # Check processors
    try:
        from github.webhook.webhook_processors.issue_webhook_processor import IssueWebhookProcessor
        processor = IssueWebhookProcessor()

        if "issues" in processor.events:
            print("✅ IssueWebhookProcessor handles 'issues' events")
        else:
            print("❌ IssueWebhookProcessor does NOT handle 'issues' events")

    except ImportError as e:
        print(f"❌ Could not import IssueWebhookProcessor: {e}")

    print("\n🎯 Summary:")
    print("- Issues should be handled by REPOSITORY webhooks (/hook/{owner}/{repo})")
    print("- Issues should NOT be handled by ORGANIZATION webhooks (/hook/org/{org_name})")
    print("- Repository webhooks are created for each individual repository")
    print("- Organization webhooks handle org-level events (members, teams, etc.)")


if __name__ == "__main__":
    verify_webhook_configuration()
