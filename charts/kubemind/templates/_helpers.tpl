{{- define "kubemind.name" -}}
kubemind
{{- end -}}

{{- define "kubemind.labels" -}}
app.kubernetes.io/name: {{ include "kubemind.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "kubemind.databaseUrl" -}}
postgresql://{{ .Values.postgres.user }}:{{ .Values.postgres.password }}@{{ include "kubemind.name" . }}-postgres:5432/{{ .Values.postgres.database }}
{{- end -}}

{{- define "kubemind.redisUrl" -}}
redis://{{ include "kubemind.name" . }}-redis:6379/0
{{- end -}}
