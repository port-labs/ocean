import os
import httpx
from datetime import datetime


JENKINS_BASE_URL = os.getenv('JENKINS_BASE_URL')
JENKINS_USERNAME = os.getenv('JENKINS_USERNAME')
JENKINS_PASSWORD = os.getenv('JENKINS_PASSWORD')


class JenkinsConnector:
    def __init__(self) -> None:
        self.jenkins_base_url = JENKINS_BASE_URL
        self.jenkins_username = JENKINS_USERNAME
        self.jenkins_password = JENKINS_PASSWORD

        auth = (JENKINS_USERNAME, JENKINS_USERNAME)
        self.httpx_client = httpx.AsyncClient(auth=auth)

    def convert_time_to_datetime(time_in_milliseconds):
        time_in_seconds = time_in_milliseconds / 1000
        return datetime.utcfromtimestamp(time_in_seconds)

    def format_job(self, job_data):
        """
        Sample:

        {
            "_class": "hudson.model.FreeStyleProject",
            "description": "My First Jenkins Project",
            "displayName": "Ivy",
            "fullDisplayName": "Ivy",
            "fullName": "Ivy",
            "name": "Ivy",
            "url": "http://localhost:8080/job/Ivy/"
        }
        """

        return {
            "jobName": job_data.get('name'),
            "jobStatus": job_data.get('url'),
            "timestamp": job_data.get('timestamp'),
            "url": job_data.get('url'),
            "jobFullUrl": job_data.get('url')
        }

    def format_build(self, build_data):
        """
        Sample:

        {
            "_class": "hudson.model.FreeStyleBuild",
            "displayName": "#4",
            "duration": 1581,
            "fullDisplayName": "Ticket Booking #4",
            "id": "4",
            "number": 4,
            "result": "SUCCESS",
            "timestamp": 1700624971639,
            "url": "http://localhost:8080/job/Ticket%20Booking/4/"
        }
        """

        timestamp = build_data.get('timestamp')
        if timestamp:
            timestamp = self.convert_time_to_datetime(timestamp)

        return {
            "buildStatus": build_data.get('result', 'UNSTABLE'),
            "buildUrl": build_data.get('url', ''),
            "timestamp": timestamp,
            "buildDuration": build_data.get('duration')
        }

    async def get_jenkins_jobs(self):
        job_url = f'{JENKINS_BASE_URL}/api/json?tree=jobs[name,url,description,displayName,fullDisplayName,fullName]'
        response = await self.httpx_client.get(job_url)

        if response.status_code == 200:
            result = response.json().get('jobs', [])

            jobs = []
            if result:
                for job_data in result:
                    jobs.append(self.format_job(job_data))
            
            return jobs
        return None

    async def get_jenkins_builds(self, job):  
        job_name = job['name'] 
        build_url = f'{JENKINS_BASE_URL}/job/{job_name}/api/json?tree=builds[id,number,url,result,duration,timestamp,displayName,fullDisplayName]'
        response = await self.httpx_client.get(build_url)

        if response.status_code == 200:
            result = response.json().get('builds', [])

            builds = []
            if result:
                for build_data in result:
                    builds.append(self.format_build(build_data))
            
            return builds
        return None