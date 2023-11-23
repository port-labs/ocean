from jenkins_integration.core.types.api_responses import (
    BuildAPIResponse,
    JobAPIResponse,
)
from jenkins_integration.core.client import JenkinsClient


def test_raw_jobs_can_be_transformed() -> None:
    raw_jobs: list[JobAPIResponse] = [
        {
            "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
            "name": "test-job",
            "url": "http://localhost:8080/job/test-job/",
            "lastBuild": {
                "_class": "org.jenkinsci.plugins.workflow.job.WorkflowRun",
                "result": "SUCCESS",
                "timestamp": 1621455067574,
            },
        }
    ]
    expected_jobs = [
        {
            "name": "test-job",
            "url": "http://localhost:8080/job/test-job/",
            "status": "SUCCESS",
            "timestamp": "2021-05-19T20:11:07.574000",
        }
    ]
    assert JenkinsClient._transform_jobs(raw_jobs) == expected_jobs


def test_raw_builds_can_be_transformed() -> None:
    raw_builds: list[BuildAPIResponse] = [
        {
            "_class": "hudson.model.FreeStyleBuild",
            "duration": 272,
            "fullDisplayName": "Stuff jub #3",
            "id": "3",
            "result": "SUCCESS",
            "timestamp": 1700649820946,
            "url": "http://localhost:8080/job/Stuff%20jub/3/",
        },
        {
            "_class": "hudson.model.FreeStyleBuild",
            "duration": 251,
            "fullDisplayName": "Stuff jub #2",
            "id": "2",
            "result": "SUCCESS",
            "timestamp": 1700649812959,
            "url": "http://localhost:8080/job/Stuff%20jub/2/",
        },
    ]
    expected_builds = [
        {
            "id": "3",
            "name": "Stuff jub #3",
            "status": "SUCCESS",
            "timestamp": "2023-11-22T10:43:40.946000",
            "url": "http://localhost:8080/job/Stuff%20jub/3/",
            "duration": "0.27 seconds",
        },
        {
            "id": "2",
            "name": "Stuff jub #2",
            "status": "SUCCESS",
            "timestamp": "2023-11-22T10:43:32.959000",
            "url": "http://localhost:8080/job/Stuff%20jub/2/",
            "duration": "0.25 seconds",
        },
    ]
    assert JenkinsClient._transform_builds(raw_builds) == expected_builds
