terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }

  backend "gcs" {
    bucket = "jpsteffe-tf-state"
    prefix = "apps/arbsplit"
  }
}

provider "google" {
  project = "jpsteffe"
  region  = "us-central1"
}
