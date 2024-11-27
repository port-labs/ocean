from typing import Any

PURE_PROJECTS: list[dict[str, Any]] = [
    {
        "key": "project-key-1",
        "name": "Project Name 1",
        "qualifier": "TRK",
        "visibility": "public",
        "lastAnalysisDate": "2017-03-01T11:39:03+0300",
        "revision": "cfb82f55c6ef32e61828c4cb3db2da12795fd767",
        "managed": False,
    },
    {
        "key": "project-key-2",
        "name": "Project Name 2",
        "qualifier": "TRK",
        "visibility": "private",
        "lastAnalysisDate": "2017-03-02T15:21:47+0300",
        "revision": "7be96a94ac0c95a61ee6ee0ef9c6f808d386a355",
        "managed": False,
    },
]


COMPONENT_PROJECTS: list[dict[str, Any]] = [
    {
        "key": "project-key-1",
        "name": "My Project 1",
        "qualifier": "TRK",
        "isFavorite": True,
        "tags": ["finance", "java"],
        "visibility": "public",
        "isAiCodeAssured": False,
        "isAiCodeFixEnabled": False,
    },
    {
        "key": "project-key-2",
        "name": "My Project 2",
        "qualifier": "TRK",
        "isFavorite": False,
        "tags": [],
        "visibility": "public",
        "isAiCodeAssured": False,
        "isAiCodeFixEnabled": False,
    },
]

ISSUES: list[dict[str, Any]] = [
    {
        "key": "01fc972e-2a3c-433e-bcae-0bd7f88f5123",
        "component": "com.github.kevinsawicki:http-request:com.github.kevinsawicki.http.HttpRequest",
        "project": "com.github.kevinsawicki:http-request",
        "rule": "java:S1144",
        "cleanCodeAttribute": "CLEAR",
        "cleanCodeAttributeCategory": "INTENTIONAL",
        "issueStatus": "ACCEPTED",
        "prioritizedRule": False,
        "impacts": [{"softwareQuality": "SECURITY", "severity": "HIGH"}],
        "message": 'Remove this unused private "getKee" method.',
        "messageFormattings": [{"start": 0, "end": 4, "type": "CODE"}],
        "line": 81,
        "hash": "a227e508d6646b55a086ee11d63b21e9",
        "author": "Developer 1",
        "effort": "2h1min",
        "creationDate": "2013-05-13T17:55:39+0200",
        "updateDate": "2013-05-13T17:55:39+0200",
        "tags": ["bug"],
        "comments": [
            {
                "key": "7d7c56f5-7b5a-41b9-87f8-36fa70caa5ba",
                "login": "john.smith",
                "htmlText": "Must be &quot;public&quot;!",
                "markdown": 'Must be "public"!',
                "updatable": False,
                "createdAt": "2013-05-13T18:08:34+0200",
            }
        ],
        "attr": {"jira-issue-key": "SONAR-1234"},
        "transitions": ["reopen"],
        "actions": ["comment"],
        "textRange": {"startLine": 2, "endLine": 2, "startOffset": 0, "endOffset": 204},
        "flows": [
            {
                "locations": [
                    {
                        "textRange": {
                            "startLine": 16,
                            "endLine": 16,
                            "startOffset": 0,
                            "endOffset": 30,
                        },
                        "msg": "Expected position: 5",
                        "msgFormattings": [{"start": 0, "end": 4, "type": "CODE"}],
                    }
                ]
            },
            {
                "locations": [
                    {
                        "textRange": {
                            "startLine": 15,
                            "endLine": 15,
                            "startOffset": 0,
                            "endOffset": 37,
                        },
                        "msg": "Expected position: 6",
                        "msgFormattings": [],
                    }
                ]
            },
        ],
        "quickFixAvailable": False,
        "ruleDescriptionContextKey": "spring",
        "codeVariants": ["windows", "linux"],
    },
    {
        "key": "01fc972e-2a3c-433e-bcae-0bd7f88f5123",
        "component": "com.github.kevinsawicki:http-request:com.github.kevinsawicki.http.HttpRequest",
        "project": "com.github.kevinsawicki:http-request",
        "rule": "java:S1144",
        "cleanCodeAttribute": "CLEAR",
        "cleanCodeAttributeCategory": "INTENTIONAL",
        "issueStatus": "ACCEPTED",
        "prioritizedRule": False,
        "impacts": [{"softwareQuality": "SECURITY", "severity": "HIGH"}],
        "message": 'Remove this unused private "getKee" method.',
        "messageFormattings": [{"start": 0, "end": 4, "type": "CODE"}],
        "line": 81,
        "hash": "a227e508d6646b55a086ee11d63b21e9",
        "author": "Developer 1",
        "effort": "2h1min",
        "creationDate": "2013-05-13T17:55:39+0200",
        "updateDate": "2013-05-13T17:55:39+0200",
        "tags": ["bug"],
        "comments": [
            {
                "key": "7d7c56f5-7b5a-41b9-87f8-36fa70caa5ba",
                "login": "john.smith",
                "htmlText": "Must be &quot;public&quot;!",
                "markdown": 'Must be "public"!',
                "updatable": False,
                "createdAt": "2013-05-13T18:08:34+0200",
            }
        ],
        "attr": {"jira-issue-key": "SONAR-1234"},
        "transitions": ["reopen"],
        "actions": ["comment"],
        "textRange": {"startLine": 2, "endLine": 2, "startOffset": 0, "endOffset": 204},
        "flows": [
            {
                "locations": [
                    {
                        "textRange": {
                            "startLine": 16,
                            "endLine": 16,
                            "startOffset": 0,
                            "endOffset": 30,
                        },
                        "msg": "Expected position: 5",
                        "msgFormattings": [{"start": 0, "end": 4, "type": "CODE"}],
                    }
                ]
            },
            {
                "locations": [
                    {
                        "textRange": {
                            "startLine": 15,
                            "endLine": 15,
                            "startOffset": 0,
                            "endOffset": 37,
                        },
                        "msg": "Expected position: 6",
                        "msgFormattings": [],
                    }
                ]
            },
        ],
        "quickFixAvailable": False,
        "ruleDescriptionContextKey": "spring",
        "codeVariants": ["windows", "linux"],
    },
]

PORTFOLIOS: list[dict[str, Any]] = [
    {
        "key": "apache-jakarta-commons",
        "name": "Apache Jakarta Commons",
        "qualifier": "VW",
        "visibility": "public",
    },
    {
        "key": "Languages",
        "name": "Languages",
        "qualifier": "VW",
        "visibility": "private",
    },
]


ANALYSIS: list[dict[str, Any]] = [
    {
        "id": "AYhSC2-LY0CHkWJxvNA9",
        "type": "REPORT",
        "componentId": "AYhNmk00XxCL_lBVBziT",
        "componentKey": "sonarsource_test_AYhCAUXoEy1XQQcbVndf",
        "componentName": "test-scanner-maven",
        "componentQualifier": "TRK",
        "analysisId": "AYhSC3WDE6ILQDIMAPIp",
        "status": "SUCCESS",
        "submittedAt": "2023-05-25T10:34:21+0200",
        "submitterLogin": "admin",
        "startedAt": "2023-05-25T10:34:22+0200",
        "executedAt": "2023-05-25T10:34:25+0200",
        "executionTimeMs": 2840,
        "hasScannerContext": True,
        "warningCount": 2,
        "warnings": [
            "The properties 'sonar.login' and 'sonar.password' are deprecated and will be removed in the future. Please pass a token with the 'sonar.token' property instead.",
            'Missing blame information for 2 files. This may lead to some features not working correctly. Please check the analysis logs and refer to <a href="https://docs.sonarsource.com/sonarqube/latest/analyzing-source-code/scm-integration/" rel="noopener noreferrer" target="_blank">the documentation</a>.',
        ],
    },
    {
        "id": "AYhSC2-LY0CHkWJxvNA9",
        "type": "REPORT",
        "componentId": "AYhNmk00XxCL_lBVBziT",
        "componentKey": "sonarsource_test_AYhCAUXoEy1XQQcbVndf",
        "componentName": "test-scanner-maven",
        "componentQualifier": "TRK",
        "analysisId": "AYhSC3WDE6ILQDIMAPIp",
        "status": "SUCCESS",
        "submittedAt": "2023-05-25T10:34:21+0200",
        "submitterLogin": "admin",
        "startedAt": "2023-05-25T10:34:22+0200",
        "executedAt": "2023-05-25T10:34:25+0200",
        "executionTimeMs": 2840,
        "hasScannerContext": True,
        "warningCount": 2,
        "warnings": [
            "The properties 'sonar.login' and 'sonar.password' are deprecated and will be removed in the future. Please pass a token with the 'sonar.token' property instead.",
            'Missing blame information for 2 files. This may lead to some features not working correctly. Please check the analysis logs and refer to <a href="https://docs.sonarsource.com/sonarqube/latest/analyzing-source-code/scm-integration/" rel="noopener noreferrer" target="_blank">the documentation</a>.',
        ],
    },
]
