terraform {
    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~> 5.0"
        }
        kubernetes = {
            source = "hashicorp/kubernetes"
            version = "~> 2.31"
        }
    }
}

provider "kubernetes" {
    config_path = "~/.kube/config"
}

provider "aws" {
    region = "eu-central-1"
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "sentinel-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["eu-central-1a", "eu-central-1b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    Project = "sentinel"
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "sentinel-cluster"
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    default = {
      min_size       = 1
      max_size       = 2
      desired_size   = 2
      instance_types = ["t3.small"]
    }
  }

  tags = {
    Project = "sentinel"
  }
}

resource "kubernetes_deployment" "redis" {
    metadata {
        name = "redis"
    }

    spec {
    replicas = 1

    selector {
      match_labels = {
        app = "redis"
      }
    }

    template {
      metadata {
        labels = {
          app = "redis"
        }
      }

      spec {
        container {
          name  = "redis"
          image = "redis:7"

          port {
            container_port = 6379
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "redis" {
  metadata {
    name = "redis"
  }

  spec {
    selector = {
      app = "redis"
    }

    port {
      port        = 6379
      target_port = 6379
    }
  }
}

resource "kubernetes_secret" "sentinel_secrets" {
  metadata {
    name = "sentinel-secrets"
  }

  data = {
    POSTGRES_PASSWORD  = "sentinel"
    GMAIL_APP_PASSWORD = var.gmail_app_password
  }

  type = "Opaque"
}

resource "kubernetes_config_map" "sentinel_config" {
  metadata {
    name = "sentinel-config"
  }

  data = {
    POSTGRES_USER   = "sentinel"
    POSTGRES_DB     = "sentinel"
    POSTGRES_HOST   = "postgres"
    REDIS_HOST      = "redis"
    GMAIL_ADDRESS   = var.gmail_address
    ALERT_TO_EMAIL  = var.alert_to_email
  }
}

resource "kubernetes_deployment" "sentinel_checker" {
  metadata {
    name = "sentinel-checker"
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "sentinel-checker"
      }
    }

    template {
      metadata {
        labels = {
          app = "sentinel-checker"
        }
      }

      spec {
        container {
          name              = "checker"
          image             = "sentinel-checker:local"
          image_pull_policy = "Never"

          env_from {
            config_map_ref {
              name = kubernetes_config_map.sentinel_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.sentinel_secrets.metadata[0].name
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_deployment" "sentinel_api" {
  metadata {
    name = "sentinel-api"
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "sentinel-api"
      }
    }

    template {
      metadata {
        labels = {
          app = "sentinel-api"
        }
      }

      spec {
        container {
          name              = "api"
          image             = "sentinel-api:local"
          image_pull_policy = "Never"

          port {
            container_port = 8000
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.sentinel_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.sentinel_secrets.metadata[0].name
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "sentinel_api" {
  metadata {
    name = "sentinel-api"
  }

  spec {
    selector = {
      app = "sentinel-api"
    }

    port {
      port        = 80
      target_port = 8000
    }
  }
}

resource "kubernetes_ingress_v1" "sentinel" {
  metadata {
    name = "sentinel-ingress"
  }

  spec {
    ingress_class_name = "nginx"

    rule {
      host = "sentinel.local"

      http {
        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.sentinel_api.metadata[0].name
              port {
                number = 80
              }
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_deployment" "sentinel_notifier" {
  metadata {
    name = "sentinel-notifier"
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "sentinel-notifier"
      }
    }

    template {
      metadata {
        labels = {
          app = "sentinel-notifier"
        }
      }

      spec {
        container {
          name              = "notifier"
          image             = "sentinel-notifier:local"
          image_pull_policy = "Never"

          env_from {
            config_map_ref {
              name = kubernetes_config_map.sentinel_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.sentinel_secrets.metadata[0].name
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "postgres" {
  metadata {
    name = "postgres"
  }

  spec {
    cluster_ip = "None"

    selector = {
      app = "postgres"
    }

    port {
      port        = 5432
      target_port = 5432
    }
  }
}

resource "kubernetes_stateful_set" "postgres" {
  metadata {
    name = "postgres"
  }

  spec {
    service_name = kubernetes_service.postgres.metadata[0].name
    replicas     = 1

    selector {
      match_labels = {
        app = "postgres"
      }
    }

    template {
      metadata {
        labels = {
          app = "postgres"
        }
      }

      spec {
        container {
          name  = "postgres"
          image = "postgres:16"

          port {
            container_port = 5432
          }

          readiness_probe {
            exec {
                command = ["pg_isready", "-U", "sentinel"]
            }
            initial_delay_seconds = 5
            period_seconds         = 5
        }

          env {
            name = "POSTGRES_USER"
            value_from {
              config_map_key_ref {
                name = kubernetes_config_map.sentinel_config.metadata[0].name
                key  = "POSTGRES_USER"
              }
            }
          }

          env {
            name = "POSTGRES_DB"
            value_from {
              config_map_key_ref {
                name = kubernetes_config_map.sentinel_config.metadata[0].name
                key  = "POSTGRES_DB"
              }
            }
          }

          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.sentinel_secrets.metadata[0].name
                key  = "POSTGRES_PASSWORD"
              }
            }
          }

          volume_mount {
            name       = "postgres-data"
            mount_path = "/var/lib/postgresql/data"
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "postgres-data"
      }

      spec {
        access_modes = ["ReadWriteOnce"]

        resources {
          requests = {
            storage = "1Gi"
          }
        }
      }
    }
  }
}