# PostProcessor

The `inline.nyl.io/v1/PostProcessor` resource can be used to configure post-processing steps for all Kubernetes
resources defined in the same [Manifest](../../glossary.md#manifest) as the `PostProcessor`. This resource does
not accept a `metadata` field.

## Prerequisites

You need the [`kyverno` CLI](https://kyverno.io/docs/kyverno-cli/) >1.13.x installed 

!!! danger
    In Kyverno 1.12.6, the `kyverno apply` command with the `-o` option outputs only the mutated resources. In
    Kyverno 1.13.2, all resources are outputted. Nyl relies on the latter behavior.

## API Spec

```yaml
apiVersion: inline.nyl.io/v1
kind: PostProcessor
metadata:
  name: my-post-processor
spec:
  # Configure Kyverno policies to apply.
  kyverno:
    # A list of files that each contain a Kyverno policy resource, usually a `ClusterPolicy`. The paths are first
    # considered relative to the manifest that this resource is defined in, and will then be searched in the project
    # search path.
    policyFiles:
    - path/to/policy.yaml

    # A mapping of policy names (what you would give as a filename) and a YAML document that represents the Kyverno
    # policy resource (usually a `ClusterPolicy`).
    inlinePolicies:
      my-policy:
        apiVersion: kyverno.io/v1
        kind: ClusterPolicy
        metadata:
          name: enforce-pod-security-context
        spec:
          rules:
          - name: my-rule
            match:
              resources:
                kinds:
                  - Pod
            validate:
              message: "Pod must have security context"
              pattern:
                spec:
                  securityContext:
                    runAsNonRoot: true

  # Define rules for a single Kyverno `ClusterPolicy` to apply. The `name` field of the rule configuration may be
  # ommited. Applies after policies defined in `kyverno`.
  #
  # To find more about Kyverno policies and rules, read https://kyverno.io/docs/writing-policies/.
  kyvernoRules:
  - match:
      resources:
        kinds:
          - Service
    mutate:
      patchStrategicMerge:
        spec:
          (type): LoadBalancer
          allocateLoadBalancerNodePorts: false
          loadBalancerClass: ngrok

```

## Example

If you're deploying to hardened RKE2, your pods must have a specific `securityContext` configuration in order to be
allowed by the PodSecurityPolicy. The application's Helm charts that you deploy may have options to inject the
required options, but if they are not you're usually out of luck unless you fork the Helm chart, or materialize
the resources and edit them in your project.

With the Nyl `PostProcessor`, you can apply Kyverno policies to validate or mutate the resources in a
[manifest](../../glossary.md#manifest).

=== "Manifest"

    ```yaml title="forgejo.yaml"
    ---
    apiVersion: inline.nyl.io/v1
    kind: PostProcessor
    spec:
      kyverno:
        policyFiles:
        - ./policies/security-profile.yaml

    ---
    apiVersion: v1
    kind: Namespace
    metadata:
      name: forgejo

    ---
    apiVersion: inline.nyl.io/v1
    kind: HelmChart
    metadata:
      name: forgejo
      namespace: forgejo
    spec:
      chart:
        repository: oci://code.forgejo.org/forgejo-helm # https://artifacthub.io/packages/helm/forgejo-helm/forgejo
        name: forgejo
        version: "10.0.1"
      values: {}
    ```

=== "Kyverno Policy"

    ```yaml title="policies/security-profile.yaml"
    apiVersion: kyverno.io/v1
    kind: ClusterPolicy
    metadata:
      name: enforce-security-context
    spec:
      validationFailureAction: enforce
      rules:
        - name: mutate-pod-security-context
          match:
            resources:
              kinds:
                - Pod
          mutate:
            patchStrategicMerge: &podSpec
              spec:
                securityContext:
                  runAsNonRoot: true
                  seccompProfile:
                    type: RuntimeDefault
                containers: &containers
                  - (name): "*"
                    securityContext:
                      runAsNonRoot: true
                      allowPrivilegeEscalation: false
                      capabilities:
                        drop:
                          - "ALL"
                initContainers: *containers
        - name: mutate-deployment-security-context
          match:
            resources:
              kinds:
                - Deployment
          mutate:
            patchStrategicMerge:
              spec:
                template: *podSpec
    ```

Running `nyl template forgejo.yaml` will use the `kyverno` CLI to apply the policy to the manifests generated by
the Helm chart. Note that the post processing happens at the very end after all other Kubernetes manifests have
been generated.
