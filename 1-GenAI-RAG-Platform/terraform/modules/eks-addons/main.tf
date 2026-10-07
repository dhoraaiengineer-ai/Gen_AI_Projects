# In-cluster platform: app namespace, AWS Load Balancer Controller, metrics-server,
# gp3 storage, and kube-prometheus-stack (Prometheus + Alertmanager + Grafana).

variable "cluster_name" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "app_namespace" {
  type = string
}

variable "prometheus_retention" {
  type = string
}

variable "alert_rules_file" {
  description = "Prometheus rule file (groups: [...]) shared with the local monitoring stack."
  type        = string
}

variable "grafana_dashboard_dir" {
  description = "Directory of Grafana dashboard JSON files shared with the local monitoring stack."
  type        = string
}

variable "chart_versions" {
  type = object({
    aws_load_balancer_controller = string
    metrics_server               = string
    kube_prometheus_stack        = string
  })
  default = {
    aws_load_balancer_controller = "3.5.0"
    metrics_server               = "3.14.0"
    kube_prometheus_stack        = "91.9.0"
  }
}

# ---------------------------------------------------------------- App namespace

resource "kubernetes_namespace_v1" "app" {
  metadata {
    name = var.app_namespace
    labels = {
      # Reject pods that don't meet the strictest built-in security profile.
      "pod-security.kubernetes.io/enforce" = "restricted"
      "pod-security.kubernetes.io/warn"    = "restricted"
    }
  }
}

# ---------------------------------------------------------------- Storage

resource "kubernetes_storage_class_v1" "gp3" {
  metadata {
    name = "gp3"
  }
  storage_provisioner    = "ebs.csi.aws.com"
  reclaim_policy         = "Delete"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true
  parameters = {
    type      = "gp3"
    encrypted = "true"
  }
}

# ---------------------------------------------------------------- AWS Load Balancer Controller

resource "aws_iam_policy" "lb_controller" {
  name   = "${var.cluster_name}-aws-load-balancer-controller"
  policy = file("${path.module}/lb-controller-iam-policy.json") # upstream policy for controller v3.5.0
}

resource "aws_iam_role" "lb_controller" {
  name = "${var.cluster_name}-aws-load-balancer-controller"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lb_controller" {
  role       = aws_iam_role.lb_controller.name
  policy_arn = aws_iam_policy.lb_controller.arn
}

resource "aws_eks_pod_identity_association" "lb_controller" {
  cluster_name    = var.cluster_name
  namespace       = "kube-system"
  service_account = "aws-load-balancer-controller"
  role_arn        = aws_iam_role.lb_controller.arn
}

resource "helm_release" "lb_controller" {
  name       = "aws-load-balancer-controller"
  namespace  = "kube-system"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = var.chart_versions.aws_load_balancer_controller

  values = [yamlencode({
    clusterName = var.cluster_name
    region      = var.region
    vpcId       = var.vpc_id
    serviceAccount = {
      create = true
      name   = "aws-load-balancer-controller"
    }
  })]

  depends_on = [aws_eks_pod_identity_association.lb_controller, aws_iam_role_policy_attachment.lb_controller]
}

# ---------------------------------------------------------------- metrics-server (for the HPA)

resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  namespace  = "kube-system"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  version    = var.chart_versions.metrics_server
}

# ---------------------------------------------------------------- Monitoring

resource "random_password" "grafana_admin" {
  length  = 24
  special = false
}

locals {
  dashboards = {
    for f in fileset(var.grafana_dashboard_dir, "*.json") :
    trimsuffix(f, ".json") => { json = file("${var.grafana_dashboard_dir}/${f}") }
  }
}

resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  namespace        = "monitoring"
  create_namespace = true
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = var.chart_versions.kube_prometheus_stack
  timeout          = 900

  values = [yamlencode({
    prometheus = {
      prometheusSpec = {
        # Pick up ServiceMonitors / rules from every namespace, not only ones labelled for this release.
        serviceMonitorSelectorNilUsesHelmValues = false
        ruleSelectorNilUsesHelmValues           = false
        retention                               = var.prometheus_retention
        resources = {
          requests = { cpu = "200m", memory = "1Gi" }
          limits   = { memory = "2Gi" }
        }
        storageSpec = {
          volumeClaimTemplate = {
            spec = {
              storageClassName = kubernetes_storage_class_v1.gp3.metadata[0].name
              accessModes      = ["ReadWriteOnce"]
              resources        = { requests = { storage = "20Gi" } }
            }
          }
        }
      }
    }

    # Same rules file as the local Prometheus.
    additionalPrometheusRulesMap = {
      "rag-api" = yamldecode(file(var.alert_rules_file))
    }

    grafana = {
      adminPassword = random_password.grafana_admin.result
      dashboardProviders = {
        "dashboardproviders.yaml" = {
          apiVersion = 1
          providers = [{
            name            = "rag"
            folder          = "RAG Platform"
            type            = "file"
            disableDeletion = true
            options         = { path = "/var/lib/grafana/dashboards/rag" }
          }]
        }
      }
      # Same dashboard JSON as the local Grafana.
      dashboards = { rag = local.dashboards }
    }
  })]

  depends_on = [kubernetes_storage_class_v1.gp3]
}

output "grafana_admin_password" {
  value     = random_password.grafana_admin.result
  sensitive = true
}
