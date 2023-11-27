import pytest
from jenkins_integration.utils import (
    produce_job_url_from_build_url,
    retrieve_batch_size_config_value,
)


def test_retrieve_batch_size_config_value_with_empty_string_will_provide_default_value() -> (
    None
):
    settings = {
        "jenkins_username": "username",
        "jenkins_password": "password",
        "jenkins_host": "host",
        "jenkins_jobs_batch_size": "",
    }
    config_key = "jenkins_jobs_batch_size"
    default_value = 100
    assert (
        retrieve_batch_size_config_value(settings, config_key, default_value)
        == default_value
    )


def test_retrieve_batch_size_config_value_will_provide_user_specified_value() -> None:
    settings = {
        "jenkins_username": "username",
        "jenkins_password": "password",
        "jenkins_host": "host",
        "jenkins_jobs_batch_size": "10",
    }
    config_key = "jenkins_jobs_batch_size"
    default_value = 100
    assert retrieve_batch_size_config_value(settings, config_key, default_value) == 10


def test_retrieve_batch_size_config_value_with_letter_will_provide_default_value() -> (
    None
):
    settings = {
        "jenkins_username": "username",
        "jenkins_password": "password",
        "jenkins_host": "host",
        "jenkins_jobs_batch_size": "asdf",
    }
    config_key = "jenkins_jobs_batch_size"
    default_value = 100
    assert (
        retrieve_batch_size_config_value(settings, config_key, default_value)
        == default_value
    )


@pytest.mark.parametrize(
    ["build_url", "expected_job_url"],
    [
        (
            "https://jenkins.example.com/job/job-name/1/",
            "https://jenkins.example.com/job/job-name/",
        ),
        (
            "https://jenkins.example.com/job/job-name/1",
            "https://jenkins.example.com/job/job-name/",
        ),
        (
            "https://jenkins.example.com/job/job-name/122",
            "https://jenkins.example.com/job/job-name/",
        ),
        (
            "https://jenkins.example.com/job/job-name/122/",
            "https://jenkins.example.com/job/job-name/",
        ),
    ],
)
def test_build_url_can_produce_job_url(build_url: str, expected_job_url: str) -> None:
    assert produce_job_url_from_build_url(build_url) == expected_job_url
