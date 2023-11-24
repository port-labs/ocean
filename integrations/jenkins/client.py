import httpx
from datetime import datetime
from port_ocean.context.ocean import ocean


class JenkinsConnector:
    def __init__(self) -> None:
        """
        Initialize JenkinsConnector class with Jenkins base URL, username, and password for authentication.
        """
        self.jenkins_base_url = ocean.integration_config["jenkins_host"]
        self.jenkins_username = ocean.integration_config["jenkins_user"]
        self.jenkins_password = ocean.integration_config["jenkins_password"]

        auth = (self.jenkins_username, self.jenkins_password)
        self.httpx_client = httpx.AsyncClient(auth=auth)

    @staticmethod
    def convert_time_to_datetime(time_in_milliseconds):
        """
        Convert time from milliseconds to a datetime object.

        Args:
        - time_in_milliseconds (int): Time in milliseconds.

        Returns:
        - datetime: Converted datetime object.
        """
        time_in_seconds = time_in_milliseconds / 1000
        return datetime.utcfromtimestamp(time_in_seconds)

    async def get_job_status(self, job_name):
         """
        Get the status of a specific Jenkins job.

        Args:
        - job_name (str): Name of the Jenkins job.

        Returns:
        - bool: Job status (True if building, False otherwise).

        Raises:
        - Exception: If failed to retrieve the job status.
        """
        job_url = f'{self.jenkins_base_url}/job/{job_name}/api/json'
        response = await self.httpx_client.get(job_url)

        if response.status_code == 200:
            job_data = response.json()
            return job_data['lastBuild']['building']
        else:
            raise Exception(f"Failed to retrieve job status: {response.status_code}")

    async def format_job(self, job_data):
         """
        Format Jenkins job data.

        Args:
        - job_data (dict): Jenkins job data.

        Returns:
        - dict: Formatted job details.
        """
        job_name = job_data.get('name')
        job_status = await self.get_job_status(job_name)  # Await the asynchronous call

        return {
            "jobName": job_name,
            "jobStatus": job_status,
            "timestamp": job_data.get('timestamp'),
            "url": job_data.get('url')
        }

    def format_build(self, build_data):
         """
        Format Jenkins build data.

        Args:
        - build_data (dict): Jenkins build data.

        Returns:
        - dict: Formatted build details.
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
        """
        Retrieve Jenkins jobs.

        Returns:
        - list: List of formatted Jenkins job details.
        """
        job_url = f'{self.jenkins_base_url}/api/json?tree=jobs[name,url,description,displayName,fullDisplayName,fullName]'
        response = await self.httpx_client.get(job_url)

        if response.status_code == 200:
            result = response.json().get('jobs', [])
            jobs = [await self.format_job(job_data) for job_data in result]
            return jobs if result else []
        return None

    async def get_jenkins_builds(self, job):
         """
        Retrieve Jenkins builds for a specific job.

        Args:
        - job (dict): Details of the Jenkins job.

        Returns:
        - list: List of formatted Jenkins build details.
        """
        job_name = job['name']
        build_url = f'{self.jenkins_base_url}/job/{job_name}/api/json?tree=builds[id,number,url,result,duration,timestamp,displayName,fullDisplayName]'
        response = await self.httpx_client.get(build_url)

        if response.status_code == 200:
            result = response.json().get('builds', [])
            builds = [self.format_build(build_data) for build_data in result]
            return builds if result else []
        return None