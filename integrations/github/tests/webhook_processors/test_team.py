# @pytest.mark.asyncio
# class TestTeamWebhookProcessor:
#     @pytest.fixture
#     def team_webhook_processor(self, mock_webhook_event: WebhookEvent) -> TeamWebhookProcessor:
#         return TeamWebhookProcessor(event=mock_webhook_event)

#     async def test_should_process_team_events(self, team_webhook_processor: TeamWebhookProcessor) -> None:
#         for action in ["created", "deleted", "edited", "added_to_repository", "removed_from_repository"]:
#             event = WebhookEvent(
#                 trace_id="test-trace-id",
#                 payload={"action": action, "team": {}},
#                 headers={"X-GitHub-Event": "team"},
#             )
#             assert await team_webhook_processor.should_process_event(event)

#     async def test_handle_team_event_with_api_call(
#         self, team_webhook_processor: TeamWebhookProcessor, resource_config: ResourceConfig
#     ) -> None:
#         team_data = {
#             "id": 1,
#             "name": "test-team",
#             "slug": "test-team"
#         }

#         mock_client = AsyncMock(spec=GitHubClient)
#         mock_client.get_single_resource.return_value = team_data

#         with patch('webhook_processors.team.GitHubClient.from_ocean_config', return_value=mock_client):
#             result = await team_webhook_processor.handle_event(
#                 {"action": "created", "team": {"slug": "test-team"}},
#                 resource_config
#             )

#             assert result.updated_raw_results == [team_data]
#             mock_client.get_single_resource.assert_called_once_with("team", "test-team")
