if (window.axios && window.Cookies) {
  window.axios.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
  window.axios.defaults.headers.common['X-CSRFToken'] = window.Cookies.get('csrftoken') || '';
}

if (window.Alpine) {
  Alpine.data('deviceDetailPage', (config) => ({
    deviceId: config.deviceId,
    status: config.initialStatus,
    rxSignal: config.rxSignal,
    txSignal: config.txSignal,
    sfpVendor: config.sfpVendor,
    partNumber: config.partNumber,
    busy: false,
    statusTick: null,
    init() {
      this.fetchStatus();
      this.statusTick = setInterval(() => this.fetchStatus(), 5000);
    },
    async fetchStatus() {
      try {
        const response = await axios.get(`/snmp/devices/${this.deviceId}/status/`);
        this.status = response.data.status || this.status;
      } catch (_err) {}
    },
    async refreshOptics() {
      this.busy = true;
      try {
        const response = await axios.post(`/snmp/devices/${this.deviceId}/optics/update/`);
        this.rxSignal = response.data.rx_signal;
        this.txSignal = response.data.tx_signal;
        this.sfpVendor = response.data.sfp_vendor;
        this.partNumber = response.data.part_number;
      } catch (_err) {
      } finally {
        this.busy = false;
      }
    },
  }));

  Alpine.data('deviceMetricsPage', (config) => ({
    deviceId: config.deviceId,
    selected: config.defaultSelection,
    applyScope: 'optical',
    chart: null,
    chartStatus: '',
    init() {
      if (this.selected) {
        this.loadChart();
      }
    },
    async loadChart() {
      if (!this.selected) {
        this.chartStatus = 'Select metric first.';
        return;
      }

      const [metric, ifIndex] = this.selected.split('|');
      let url = `/snmp/api/devices/${this.deviceId}/timeseries?metric=${encodeURIComponent(metric)}&limit=200`;
      if (ifIndex) {
        url += `&if_index=${encodeURIComponent(ifIndex)}`;
      }

      this.chartStatus = 'Loading...';
      try {
        const response = await axios.get(url);
        const points = response.data
          .map((row) => ({
            ts: row.ts,
            value: row.value_float !== null && row.value_float !== undefined
              ? row.value_float
              : Number.parseFloat(row.value_text),
          }))
          .filter((p) => !Number.isNaN(p.value))
          .reverse();

        if (!points.length) {
          this.chartStatus = 'No numeric samples yet for selected metric.';
          if (this.chart) {
            this.chart.destroy();
            this.chart = null;
          }
          return;
        }

        const labels = points.map((p) => p.ts);
        const values = points.map((p) => p.value);

        if (this.chart) {
          this.chart.destroy();
        }

        this.chart = new Chart(this.$refs.metricChart, {
          type: 'line',
          data: {
            labels,
            datasets: [{
              label: ifIndex ? `${metric} (ifIndex ${ifIndex})` : metric,
              data: values,
              borderColor: '#2563eb',
              borderWidth: 2,
              pointRadius: 0,
              tension: 0.25,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
              x: { display: false },
              y: { beginAtZero: false },
            },
          },
        });

        this.chartStatus = `Loaded ${points.length} points.`;
      } catch (_err) {
        this.chartStatus = 'Failed to load timeseries.';
      }
    },
  }));
}
