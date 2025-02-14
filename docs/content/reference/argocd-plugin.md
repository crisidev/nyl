# ArgoCD Plugin

  [0]: https://argo-cd.readthedocs.io/en/latest/operator-manual/config-management-plugins/

This page describes Nyl's integration as an [ArgoCD ConfigManagementPlugin][0].

## Installation

Config management plugins are installed as additional containers to the `argocd-repo-server` Pod. They launch the
`argocd-cmp-server` binary and communicates with ArgoCD over gRPC via a socket file shared between the repo-server
and the plugin container under `/home/argocd/cmp-server/plugins`.

We recommend the following configuration:

```yaml title="argocd-values.yaml"
repoServer:
  extraContainers:
    - name: nyl-v1
      image: ghcr.io/helsing-ai/nyl/argocd-cmp:{{ NYL_VERSION }}
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
      volumeMounts:
        - mountPath: /var/run/argocd
          name: var-files
        - mountPath: /home/argocd/cmp-server/plugins
          name: plugins
        - mountPath: /tmp
          name: cmp-tmp
      envFrom:
        - secretRef:
            name: argocd-nyl-env
      env:
        - name: NYL_CACHE_DIR
          value: /tmp/nyl-cache
        - name: NYL_LOG_LEVEL
          value: info
  clusterRoleRules:
    enabled: true
  volumes:
    - name: cmp-tmp
      emptyDir: {}
```

!!! warning

    The `clusterRoleRules.enabled=true` option enables the plugin to access the Kubernetes API. This is necessary for
    various Nyl features to function correctly (such as lookups, see [Cluster connectivity](./cluster-connectivity.md)).
    If you do not wish to grant the plugin access to the Kubernetes API, you must disable this option and ensure that
    your manifests do not rely on features that require API access.

## Discovery

The ArgoCD plugin runs `nyl argocd discovery` as the discovery command to determine if a repository is compatible with
Nyl. This means that if you create an ArgoCD application that points to a Git repository with at least one Nyl
configuration file in it, the plugin will be invoked implicitly without specifying the `nyl-v1` plugin name in the
application spec.

## One file per application

ArgoCD applications do not permit to point their `source.path` field to a file within a repository, it must be a
directory. For this, Nyl accepts a `ARGOCD_ENV_NYL_CMP_TEMPLATE_INPUT` environment variable that can be a comma-separate
list of filenames that you would pass to `nyl template` as arguments. Nyl will then ignore the default `.` argument
(pointing to the current directory, which is the directory specified with `source.path`) and use the files specified
via the environment variable instead.

```yaml title="argocd-application.yaml"
# trimmed example
spec:
  source:
    plugin:
      name: nyl-v1
      env:
        - name: NYL_CMP_TEMPLATE_INPUT
          value: '{{.path.filename}}'
```

## ApplicationSet example

A desirable pattern for using Nyl with ArgoCD is to create on application per YAML file in the directory corresponding
to your cluster in the repository. The following example demonstrates how to setup an ArgoCD `ApplicationSet` that
does exactly this:

```yaml title="appset.yaml"
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: main
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
  - git:
      repoURL: git@github.com:myorg/gitops.git
      revision: HEAD
      files:
        - path: "clusters/my-cluster/*.yaml"
  template:
    metadata:
      name: '{{.path.filename | trimSuffix ".yaml" | slugify }}'
    spec:
      project: default
      source:
        repoURL: git@github.com:myorg/gitops.git
        targetRevision: HEAD
        path: '{{.path.path}}'
        plugin:
          name: nyl-v1
          env:
            - name: NYL_CMP_TEMPLATE_INPUT
              value: '{{.path.filename}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{.path.basename}}'
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
          - ServerSideApply=true
```

You may treat `appset.yaml` as a member of the same directory, allowing it to be managed by its own "appset" application
created by the `ApplicationSet` itself.

Note that in order for the `argocd-applicationset-controller` to be able to clone your Git repository via SSH, you
need to configure a [Credential template](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/#credential-templates)
that matches the `spec.generators[0].git.repoURL` field, whereas for the individual applications to clone the repository
you need to configure a [Repository](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/#repositories).

```yaml title="repository-secrets.yaml"
# For the ApplicationSet
---
kind: Secret
metadata:
  name: github-creds
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repo-creds
type: Opaque
stringData:
  project: default
  name: github.com
  url: git@github.com:myorg/
  type: git
  sshPrivateKey: ...

# For the Application(s), but credentials can be omitted as they are inherited from the repo-creds above.
---
kind: Secret
metadata:
  name: github-repo-gitops
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  project: default
  type: git
  url: git@github.com:myorg/gitops.git
```

## Debugging the plugin

The ArgoCD plugin produces per-project/application logs in the `/var/log` directory of the `nyl-v1` container in the
`argocd-repo-server` pod. These logs are often much easier to inspect than the output the template rendering fails
and ArgoCD reports stderr to the UI.

At the start of each invokation of Nyl, the command will debug-log some useful basic information:

* The command-line used to invoke Nyl.
* The current working directory.
* All Nyl-relevant environment variables (such that start with `ARGOCD_`, `NYL_` and `KUBE_`).

At the end Nyl will also print the command-line again as well as the time it took for the command to complete.
Note that in order to see these logs you should set the `NYL_LOG_LEVEL` environment variable to `debug`.
