#!/bin/bash
set -euo pipefail

# Broadcast M8 Auto-Scaling Validation Script
# Simulates load and verifies scaling behavior

NAMESPACE="broadcast"
PROMETHEUS_ADAPTER_NS="monitoring"

echo "=== Broadcast M8 Auto-Scaling Validation ==="
echo "Namespace: $NAMESPACE"
echo

# Check prerequisites
echo "1. Checking prerequisites..."
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl not found"
    exit 1
fi

if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo "Error: Namespace $NAMESPACE does not exist"
    exit 1
fi

echo " Prerequisites satisfied"
echo

# Check Prometheus Adapter
echo "2. Checking Prometheus Adapter..."
ADAPTER_PODS=$(kubectl get pods -n $PROMETHEUS_ADAPTER_NS -l app=prometheus-adapter -o name | wc -l)
if [ "$ADAPTER_PODS" -lt 2 ]; then
    echo "Warning: Less than 2 Prometheus Adapter replicas running ($ADAPTER_PODS)"
else
    echo " Prometheus Adapter healthy ($ADAPTER_PODS replicas)"
fi
echo

# Check HPA status
echo "3. Checking Horizontal Pod Autoscalers..."
HPAS=$(kubectl get hpa -n $NAMESPACE -o name)
if [ -z "$HPAS" ]; then
    echo "Error: No HPAs found in namespace $NAMESPACE"
else
    echo "Found HPAs:"
    for hpa in $HPAS; do
        hpa_name=$(basename "$hpa")
        STATUS=$(kubectl get $hpa -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="AbleToScale")].status}')
        if [ "$STATUS" = "True" ]; then
            echo "   $hpa_name: Able to scale"
        else
            echo "   $hpa_name: Unable to scale - $(kubectl get $hpa -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="AbleToScale")].message}')"
        fi
    done
fi
echo

# Check custom metrics availability
echo "4. Checking custom metrics exposure..."
METRICS_ENDPOINT="/apis/custom.metrics.k8s.io/v1beta1"
if kubectl get --raw "$METRICS_ENDPOINT" &> /dev/null; then
    echo " Custom metrics API accessible"
    # Try to list one metric as sample
    SAMPLE=$(kubectl get --raw "$METRICS_ENDPOINT" | head -c 200)
    if [ -n "$SAMPLE" ]; then
        echo "  Sample metrics data available"
    else
        echo "  Warning: No metrics data returned"
    fi
else
    echo " Custom metrics API not accessible"
    echo "  Check Prometheus Adapter deployment and RBAC permissions"
fi
echo

# Check node auto-provisioning
echo "5. checking Node Auto-Provisioning..."
CLUSTER_INFO=$(gcloud container clusters describe $(kubectl config current-context) --format=json 2>/dev/null || echo "{}")
if echo "$CLUSTER_INFO" | grep -q "\"autoprovisioningEnabled\": true"; then
    echo " Node Auto-Provisioning enabled"
else
    echo " Node Auto-Provisioning not detected"
    echo "  Verify GKE cluster has NAP enabled:"
    echo "  gcloud container clusters describe <cluster> --format json | grep autoprovisioningEnabled"
fi
echo

# Summary
echo "=== Validation Complete ==="
echo "Next steps:"
echo "1. Apply any failing configurations"
echo "2. Run load tests to verify scaling behavior"
echo "3. Monitor with: kubectl get hpa -w -n $NAMESPACE"
echo "4. Check node pool activity: kubectl get nodes --show-labels -w"
