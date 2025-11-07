# Harbor Project
resource "port_blueprint" "project" {
  identifier = "harborProject"
  title      = "Harbor Project"
  icon       = "Project"

  properties = {
    name = {
      type  = "string"
      title = "Name"
    }
    visibility = {
      type  = "string"
      title = "Visibility"
      enum  = ["public", "private"]
    }
    creation_time = {
      type  = "date-time"
      title = "Creation Time"
    }
    project_id = {
      type  = "number"
      title = "Project ID"
    }
  }
}

# Harbor Repository
resource "port_blueprint" "repository" {
  identifier = "harborRepository"
  title      = "Harbor Repository"
  icon       = "Repository"

  properties = {
    name = {
      type  = "string"
      title = "Name"
    }
    project_name = {
      type  = "string"
      title = "Project Name"
    }
    pull_count = {
      type  = "number"
      title = "Pull Count"
    }
    creation_time = {
      type  = "date-time"
      title = "Creation Time"
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
    size = {
      type  = "number"
      title = "Size (bytes)"
    }
    push_time = {
      type  = "date-time"
      title = "Push Time"
    }
    vulnerability_summary = {
      type  = "object"
      title = "Vulnerability Summary"
    }
    severity = {
      type  = "string"
      title = "Max Severity"
      enum  = ["none", "unknown", "negligible", "low", "medium", "high", "critical"]
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
  }
}
