// Rollback is a git revert of the spec and a rerun of this pipeline.
// Mesh config pipeline: validate the traffic spec, render and analyze, apply to staging, run the BDD suite, then promote.
pipeline {
  agent any
  options { timestamps(); timeout(time: 30, unit: 'MINUTES'); disableConcurrentBuilds() }
  stages {
    stage('Validate') {
      steps { sh 'python3 -m meshctl validate mesh/traffic.yaml && python3 -m meshctl validate mesh/pay.yaml && python3 -m pytest -q tests' }
    }
    stage('Analyze') {
      steps { sh 'python3 -m meshctl render mesh/traffic.yaml > rendered.yaml && istioctl analyze --use-kube=false rendered.yaml' }
    }
    stage('Staging') {
      steps { sh 'python3 -m meshctl apply mesh/traffic.yaml && python3 -m behave features' }
    }
    stage('Promote') {
      when { branch 'main' }
      input { message 'Apply to production?'; ok 'Apply' }
      steps { sh 'KUBECONFIG=$PROD_KUBECONFIG python3 -m meshctl apply mesh/traffic.yaml' }
    }
  }
  post {
    always { archiveArtifacts artifacts: 'rendered.yaml', allowEmptyArchive: true }
  }
}
