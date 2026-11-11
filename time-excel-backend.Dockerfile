FROM cr-portal-backend:time-excel-before-20261111-1igozs
COPY reports.py /app/src/cr_portal/api/v1/reports.py
COPY time_report_export.py /app/src/cr_portal/services/time_report_export.py
