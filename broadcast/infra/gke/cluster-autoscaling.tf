terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
  default     = "broadcast-cluster"
}

variable "initial_node_count" {
  description = "Initial number of nodes per zone"
  type        = number
  default     = 1
}

resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.region

  remove_default_node_pool = true
  initial_node_count       = 1

  # Network configuration (set network/subnetwork when using custom VPC)
  # network    = var.network
  # subnetwork = var.subnetwork

  # Enable the Horizontal Pod Autoscaler addon
  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
  }

  # Enable workload identity for secure access to Google Cloud services
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Enable binary authorization for container image validation
  binary_authorization {
    evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"
  }

  # Set minimum master version for stable GKE release channel
  min_master_version = "1.29"

  # Enable Node Auto-Provisioning (NAP) at the cluster level
  cluster_autoscaling {
    enabled = true
    auto_provisioning_defaults {
      oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
      shielded_instance_config {
        enable_secure_boot = true
      }
    }
    resource_limits {
      resource_type = "cpu"
      minimum       = 1
      maximum       = 100
    }
    resource_limits {
      resource_type = "memory"
      minimum       = 1
      maximum       = 512
    }
  }
}

# Node Pool for system components (core DNS, metrics-server, etc.)
resource "google_container_node_pool" "primary_nodes" {
  name       = "${var.cluster_name}-default-pool"
  cluster    = google_container_cluster.primary.name
  node_count = var.initial_node_count

  node_config {
    machine_type = "e2-medium"
    # Enable workload identity
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    # Enable shielded nodes for increased security
    shielded_instance_config {
      enable_secure_boot = true
    }
    # OAuth scopes for node agents
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]
  }

  # Enable node auto-upgrades and auto-repair
  management {
    auto_repair  = true
    auto_upgrade = true
  }

  # Enable autoscaling on this node pool
  autoscaling {
    min_node_count = 1
    max_node_count = 5
  }
}

# Output useful information
output "cluster_name" {
  value = google_container_cluster.primary.name
}

output "cluster_endpoint" {
  value = google_container_cluster.primary.endpoint
}

output "cluster_master_version" {
  value = google_container_cluster.primary.master_version
}
