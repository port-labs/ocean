# Harbor Project
resource "port_blueprint" "project" {
  identifier = "harborProject"
  title      = "Harbor Project"
  icon       = "Project"

  properties = {
    project_id = {
      type  = "number"
      title = "Project ID"
    }

    name = {
      type  = "string"
      title = "Name"
    }

    owner_id = {
      type  = "number"
      title = "Owner ID"
    }


    owner_name = {
      type  = "string"
      title = "Owner Name"
    }

    registry_id = {
      type  = "number"
      title = "Registry ID"
    }

    creation_time = {
      type  = "date-time"
      title = "Creation Time"
    }

    update_time = {
      type  = "date-time"
      title = "Update Time"
    }

    repo_count = {
      type  = "number"
      title = "Repository Count"
    }

    is_public = {
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

    project_id = {
      type  = "number"
      title = "Project ID"
    }

    description = {
      type  = "string"
      title = "Description"
    }

    artifact_count = {
      type  = "number"
      title = "Artifact Count"
    }

    pull_count = {
      type  = "number"
      title = "Pull Count"
    }
    creation_time = {
      type  = "date-time"
      title = "Creation Time"
    }

    update_time = {
      type  = "date-time"
      title = "Update Time"
    }
  }

  relations = {
    project = {
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
    media_type = {
      type  = "string"
      title = "Media Type"
    }
    manifest_media_type = {
      type  = "string"
      title = "Manifest Media Type"
    }
    
    size = {
      type  = "number"
      title = "Size (bytes)"
    }

    pull_time = {
      type  = "date-time"
      title = "Pull Time"
    }

    push_time = {
      type  = "date-time"
      title = "Push Time"
    }
    
    total_vulnerabilities = { 
      type = "number", 
      title = "Total Vulnerabilities" 
    }
    
    scanners = { 
      type = "array", 
      title = "Scanners",
      items = { type = "string" }
    }

    max_severity = {
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
    repository = {
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

    user_id = {
      type  = "number"
      title = "User ID"
    }

    realname = {
      type  = "string"
      title = "Real Name"
    }

    sysadmin_flag = {
      type  = "boolean"
      title = "Sysadmin Flag"
    }

    admin_role_in_auth = {
      type  = "boolean"
      title = "Admin Role In Auth"
    }

    creation_time = {
      type  = "date-time"
      title = "Creation Time"
    }

    comment = {
      type  = "string"
      title = "Comment"
    }

    update_time = {
      type  = "date-time"
      title = "Update Time"
    }
  }
}
