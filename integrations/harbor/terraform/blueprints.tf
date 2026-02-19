# Harbor Project
resource "port_blueprint" "project" {
  identifier = "harborProject"
  title      = "Harbor Project"
  icon       = "Project"

  properties = {
    projectId = {
      type  = "number"
      title = "Project ID"
    }

    name = {
      type  = "string"
      title = "Name"
    }

    ownerId = {
      type  = "number"
      title = "Owner ID"
    }


    ownerName = {
      type  = "string"
      title = "Owner Name"
    }

    registryId = {
      type  = "number"
      title = "Registry ID"
    }

    creationTime = {
      type  = "date-time"
      title = "Creation Time"
    }

    updateTime = {
      type  = "date-time"
      title = "Update Time"
    }

    repoCount = {
      type  = "number"
      title = "Repository Count"
    }

    isPublic = {
      type  = "boolean"
      title = "Is Public"
    }

    togglable = {
      type  = "boolean"
      title = "Togglable"
    }

    deleted = {
      type  = "boolean"
      title = "Deleted"
    }
  }

  relations = {
  }
}

# Harbor Repository
resource "port_blueprint" "repository" {
  identifier = "harborRepository"
  title      = "Harbor Repository"
  icon       = "Repository"

  properties = {
    id = {
      type  = "number"
      title = "ID"
    }
    name = {
      type  = "string"
      title = "Name"
    }

    full_name = {
      type  = "string"
      title = "Full Name"
    }

    projectId = {
      type  = "number"
      title = "Project ID"
    }

    description = {
      type  = "string"
      title = "Description"
    }

    artifactCount = {
      type  = "number"
      title = "Artifact Count"
    }

    pullCount = {
      type  = "number"
      title = "Pull Count"
    }
    creationTime = {
      type  = "date-time"
      title = "Creation Time"
    }

    updateTime = {
      type  = "date-time"
      title = "Update Time"
    }
  }

  relations = {
    harborProject = {
      title  = "Project"
      target = "harborProject"
      many   = false
    }
  }

  depends_on = [ port_blueprint.project ]
}

# Harbor Artifact
resource "port_blueprint" "artifact" {
  identifier = "harborArtifact"
  title      = "Harbor Artifact"
  icon       = "Docker"

  properties = {
    id = {
      type  = "number"
      title = "ID"
    }
    digest = {
      type  = "string"
      title = "Digest"
    }
    tags = {
      type  = "array"
      title = "Tags"
      items = { type = "string" }
    }
    mediaType = {
      type  = "string"
      title = "Media Type"
    }
    manifestMediaType = {
      type  = "string"
      title = "Manifest Media Type"
    }

    size = {
      type  = "number"
      title = "Size (bytes)"
    }

    pullTime = {
      type  = "date-time"
      title = "Pull Time"
    }

    pushTime = {
      type  = "date-time"
      title = "Push Time"
    }

    totalVulnerabilities = {
      type = "number",
      title = "Total Vulnerabilities"
    }

    scanners = {
      type = "array",
      title = "Scanners",
      items = { type = "string" }
    }

    maxSeverity = {
      type  = "string"
      title = "Max Severity"
      enum  = ["none", "unknown", "negligible", "low", "medium", "high", "critical"]
    }

    type = {
      type  = "string"
      title = "Type"
    }

    icon = {
      type  = "string"
      title = "Icon"
    }

    latest_tag = {
      type  = "string"
      title = "Latest Tag"
    }
  }

  relations = {
    harborRepository = {
      title  = "Repository"
      target = "harborRepository"
      many   = false
    }
  }

  depends_on = [ port_blueprint.repository ]
}

# Harbor User
resource "port_blueprint" "user" {
  identifier = "harborUser"
  title      = "Harbor User"
  icon       = "User"

  properties = {
    username = {
      type  = "string"
      title = "Username"
    }

    email = {
      type  = "string"
      title = "Email"
    }

    userId = {
      type  = "number"
      title = "User ID"
    }

    realname = {
      type  = "string"
      title = "Real Name"
    }

    sysadminFlag = {
      type  = "boolean"
      title = "Sysadmin Flag"
    }

    adminRoleInAuth = {
      type  = "boolean"
      title = "Admin Role In Auth"
    }

    creationTime = {
      type  = "date-time"
      title = "Creation Time"
    }

    comment = {
      type  = "string"
      title = "Comment"
    }

    updateTime = {
      type  = "date-time"
      title = "Update Time"
    }
  }
}
