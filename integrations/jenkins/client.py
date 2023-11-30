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
        try:
            response = await self.httpx_client.get(job_url)

            if response.status_code == 200:
                job_data = response.json()
                return job_data['lastBuild']['building']
            else:
                response.raise_for_status()  # Raise an error for non-2xx status codes

        except httpx.HTTPError as http_err:
            raise Exception(f"Failed to retrieve job status for {job_name}: {http_err}") from None
        except Exception as err:
            raise Exception(f"An error occurred while fetching job status: {err}") from None

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
        display_name = job_data.get('displayName')  # Access displayName directly
        full_name = job_data.get('fullName')  # Access fullName directly

        return {
            "jobName": job_name,
            "jobStatus": job_status,
            "timestamp": job_data.get('timestamp'),
            "url": job_data.get('url'),
            "displayName": display_name,
            "fullName": full_name
        }

    def format_build(self, build_data):
        """
        Format Jenkins build data.

        Args:
        - build_data (dict): Jenkins build data.

        Returns:
        - dict: Formatted build details.
        """
        display_name = build_data.get('displayName')
        full_display_name = build_data.get('fullDisplayName')
        timestamp = build_data.get('timestamp')
        if timestamp:
            timestamp = self.convert_time_to_datetime(timestamp)

        return {
            "buildStatus": build_data.get('result', 'UNSTABLE'),
            "buildUrl": build_data.get('url', ''),
            "timestamp": timestamp,
            "buildDuration": build_data.get('duration'),
            "displayName": display_name,
            "fullDisplayName": full_display_name
        }

    async def get_jenkins_jobs(self):
        """
        Retrieve Jenkins jobs.

        Returns:
        - list: List of formatted Jenkins job details.
        """
        jobs = []
        job_url = f'{self.jenkins_base_url}/api/json?tree=jobs[name,url,description,displayName,fullDisplayName,fullName]'
        start_index = 0

        while True:
            try:
                response = await self.httpx_client.get(f'{job_url}&start={start_index}')
                
                if response.status_code == 200:
                    result = response.json().get('jobs', [])
                    formatted_jobs = [await self.format_job(job_data) for job_data in result]
                    jobs.extend(formatted_jobs)
                    start_index += len(result)
                    
                    if not result:
                        break
                else:
                    response.raise_for_status()  # Raise an error for non-2xx status codes
            
            except httpx.HTTPError as http_err:
                raise Exception(f"Failed to retrieve Jenkins jobs: {http_err}") from None
            except Exception as err:
                raise Exception(f"An error occurred while fetching Jenkins jobs: {err}") from None

        return jobs

    async def get_jenkins_builds(self, job):
        """
        Retrieve Jenkins builds for a specific job.

        Args:
        - job (dict): Details of the Jenkins job.

        Returns:
        - list: List of formatted Jenkins build details.
        """
        builds = []
        job_name = job['jobName']
        build_url = f'{self.jenkins_base_url}/job/{job_name}/api/json?tree=builds[id,number,url,result,duration,timestamp,displayName,fullDisplayName]'
        start_index = 0

        while True:
            try:
                response = await self.httpx_client.get(f'{build_url}&start={start_index}')
                
                if response.status_code == 200:
                    result = response.json().get('builds', [])
                    formatted_builds = [self.format_build(build_data) for build_data in result]
                    builds.extend(formatted_builds)
                    start_index += len(result)
                    
                    if not result:
                        break
                else:
                    response.raise_for_status()  # Raise an error for non-2xx status codes
            
            except httpx.HTTPError as http_err:
                raise Exception(f"Failed to retrieve Jenkins builds: {http_err}") from None
            except Exception as err:
                raise Exception(f"An error occurred while fetching Jenkins builds: {err}") from None