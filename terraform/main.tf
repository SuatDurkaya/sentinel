terraform {
    required_providers {
        kubernetes = {
            source = "hashicorp/kubernetes"
            version = "~> 2.31"
        }
    }
}

provider "kubernetes" {
    config_path = "~/.kube/config"
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