# AutoFlow AWS Infrastructure (Terraform)

This is the layer *below* `k8s/` — those manifests assume a cluster,
managed Postgres, and managed Redis already exist. This creates them.

## Apply order

```
cd infra/terraform/aws
terraform init
terraform plan  -var="billing_alert_email=you@yourcompany.com"
terraform apply -var="billing_alert_email=you@yourcompany.com"
```

Then, once the EKS cluster exists:
```
aws eks update-kubeconfig --name <output.eks_cluster_endpoint's cluster name>
kubectl apply -k ../../../k8s/overlays/production
```

## Before your first real apply

1. **Uncomment the S3 backend block** in `main.tf` and create the state
   bucket + DynamoDB lock table first (chicken-and-egg: bootstrap those
   two resources manually or via a separate, tiny Terraform config —
   don't try to have this config manage its own state backend).
2. **Set `billing_alert_email`** — there's no default on purpose, so this
   can't apply with cost alerts silently going nowhere.
3. **Set `monthly_budget_usd`** to your real expected spend. The default
   ($2000) is a placeholder, not a recommendation.
4. **Review `endpoint_public_access`** in `modules/eks` — it defaults to
   open; restrict `public_access_cidrs` to your office/VPN range before
   running this against real production traffic.

## Multi-region (opt-in, not applied by default)

`modules/multi-region` is not wired into root `main.tf` — it roughly
doubles your database/compute cost for standby capacity, so it's meant
to be turned on deliberately, not by default. To enable it:

1. Apply this same root config a second time with `-var="aws_region=us-west-2"`
   and a separate state file/workspace, to stand up a scaled-down copy of
   the stack in the secondary region.
2. Add a `module "multi_region"` block to root `main.tf` pointing at both
   regions' API load balancer DNS names.
3. See `modules/multi-region/promote.sh` for the (deliberately manual,
   not automatic) database promotion step during an actual failover, and
   `DR_RUNBOOK.md` for the full procedure.

## What this does NOT do

- Does not manage DNS zone creation (`hosted_zone_id` is a variable —
  bring your own Route53 zone).
- Does not manage container image builds/pushes — that's
  `.github/workflows/ci-cd.yml`.
- Does not manage k8s-level resources (namespaces, deployments,
  NetworkPolicies) — that's `k8s/`, applied separately after this.
