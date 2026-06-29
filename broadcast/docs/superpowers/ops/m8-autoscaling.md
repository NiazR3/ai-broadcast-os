# M8 Auto-Scaling Operations Runbook

## Overview
This document provides operational guidance for managing the auto-scaling system of the AI Broadcast OS platform on GKE.

## Monitoring Autoscaling Health

### Checking HPA Status
```bash
# View all HPAs in the broadcast namespace
kubectl get hpa -n broadcast

# Describe a specific HPA for detailed status
kubectl describe hpa broadcast-service-hpa -n broadcast
```

### Checking Cluster Autoscaler & NAP Status
```bash
# View cluster autoscaler events
kubectl get events --field-source=cluster-autoscaler

# View node pools (including auto-provisioned ones)
kubectl get nodes --show-labels

# Check NAP activity in GKE console or via gcloud
gcloud container operations list --zone=<zone> --filter="operationType=AUTO_PROVISION"
```

### Viewing Custom Metrics
```bash
# Check if custom metrics are exposed
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1" | jq .

# Query specific metric (replace with actual metric name)
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/broadcast/pods/*/broadcast_viewer_count_total" | jq .
```

## Tuning Guidelines

### Adjusting HPA Targets
To change the target value for a metric:
1. Edit the corresponding HPA YAML file in `infra/k8s/hpa/`
2. Update the `averageValue` in the external metric target
3. Apply the changes: `kubectl apply -f <filename>.yaml`
4. Monitor the effects for 15-30 minutes before making further adjustments

### Recommended Starting Points
| Service | Metric | Initial Target | Notes |
|---------|--------|----------------|-------|
| broadcast-service | viewer_count_total | 100 viewers/pod | Adjust based on actual resource usage per viewer |
| media-agent | transcoding_load | 50 jobs/pod | Monitor CPU usage; may need GPU nodes for heavy transcoding |
| research-agent | research_queue_depth | 20 tasks/pod | Adjust based on average task duration |
| audience-agent | chat_messages_per_second | 100 msg/sec/pod | Consider message complexity (text vs. media) |

### Adjusting Scale Behavior
To make scaling more or less aggressive:
- **ScaleUp stabilizationWindowSeconds**: Decrease for faster response (risk of thrashing)
- **ScaleDown stabilizationWindowSeconds**: Increase to prevent premature scale-down
- **Policies values**: Adjust Pods or Percent values to change batch sizes

## Troubleshooting

### HPA Not Scaling
**Symptoms:** Pod count remains constant despite changing metrics
**Checks:**
1. Verify metrics are exposed: `kubectl get --raw "/apis/custom.metrics`
2. Check HPA conditions: `kubectl describe hpa <name>`
3. Look for missing or incorrect metric labels
4. Verify Prometheus Adapter is running and scraping metrics
5. Check resource metrics (CPU/memory) as fallback

### Scaling Too Slow
**Symptoms:** Pods pending due to insufficient resources
**Checks:**
1. Verify NAP is enabled: `gcloud container clusters describe <cluster>`
2. Check node pool quotas in GCP project
3. Look for scheduling errors: `kubectl describe pod <pending-pod>`
4. Check if pod requests exceed available node types in region

### Scaling Too Fast / Thrashing
**Symptoms:** Rapid scale-up/scale-down cycles
**Checks:**
1. Increase stabilization windows in HPA
2. Increase scale-down delay in NAP (managed via GKE settings)
3. Verify metric temporal smoothing (consider using moving averages)
4. Check for metric spikes due to instrumentation issues

### No Custom Metrics Available
**Symptoms:** HPA fails with "failed to get external metric"
**Checks:**
1. Prometheus Adapter pods running: `kubectl get pods -n monitoring`
2. Adapter can reach Prometheus: Check adapter logs for scrape errors
3. Prometheus scraping broadcast services: Check Prometheus targets
4. Broadcast services exposing `/metrics` endpoint
5. RBAC permissions for adapter to read services/endpoints/pods

## Cost Optimization Tips

1. **Set appropriate maxReplicas**: Prevent runaway scaling during metric errors
2. **Use realistic minReplicas**: Don't oversize for baseline traffic
3. **Monitor node utilization**: Use GKE dashboards to identify over/under-provisioned nodes
4. **Consider spot/preemptible nodes**: For fault-tolerant workloads (research agent batch jobs)
5. **Schedule known broadcasts**: Use time-based scaling for regular events (M9+ feature)

## Integration with Monitoring (M6)
- Ensure Grafana dashboards include:
  - HPA desired vs. actual replica counts
  - Autoscaler events (scale-up/scale-down)
  - Custom metric trends
  - Node pool usage and costs
- Set up alerts for:
  - HPA at maxReplicas for extended periods
  - Failed metric retrieval (adapter or service issues)
  - Node provisioning failures (quota or permission issues)
  - Extended periods of unschedulable pods

## Rollback Procedure
If autoscaling causes issues:
1. Temporarily set maxReplicas = currentReplicas in all HPAs
2. Drain problematic node pools if needed
3. Fix underlying issue (metric, resource requests, etc.)
4. Gradually restore normal HPA configuration
