import React from 'react';
import ReactApexChart from 'react-apexcharts';

interface InteractiveChartProps {
  chartData: any[];
  chartPeriod: string;
  setChartPeriod: (period: string) => void;
  targetPrice: number;
  stopLoss: number;
}

export const InteractiveChart: React.FC<InteractiveChartProps> = ({
  chartData,
  chartPeriod,
  setChartPeriod,
  targetPrice,
  stopLoss
}) => {
  const annotations = {
    yaxes: [
      {
        y: targetPrice,
        borderColor: '#22e07a',
        label: {
          borderColor: '#1a7a48',
          style: { color: '#22e07a', background: '#0d1a12', fontSize: '10px' },
          text: `TARGET ${targetPrice.toLocaleString('id-ID')}`
        }
      },
      {
        y: stopLoss,
        borderColor: '#ff5c5c',
        label: {
          borderColor: '#5c2323',
          style: { color: '#ff5c5c', background: '#1a0d0d', fontSize: '10px' },
          text: `STOP LOSS ${stopLoss.toLocaleString('id-ID')}`
        }
      }
    ]
  };

  const chartOptions: any = {
    chart: {
      type: 'candlestick',
      background: 'transparent',
      toolbar: { show: false },
      animations: {
        enabled: true,
        easing: 'linear',
        speed: 300,
        dynamicAnimation: {
          enabled: true,
          speed: 300
        }
      }
    },
    theme: { mode: 'dark' },
    plotOptions: {
      candlestick: {
        colors: { upward: '#22e07a', downward: '#ff5c5c' },
        wick: { useFillColor: true }
      }
    },
    annotations: annotations,
    xaxis: {
      type: 'datetime',
      labels: { style: { colors: '#8a958c', fontSize: '10px' } },
      axisBorder: { show: false }, axisTicks: { show: false }
    },
    yaxis: {
      tooltip: { enabled: true },
      labels: {
        style: { colors: '#8a958c', fontSize: '10px' },
        formatter: (val: number) => val ? val.toLocaleString('id-ID') : ''
      }
    },
    grid: { borderColor: '#1e2621', strokeDashArray: 4 }
  };

  return (
    <>
      <div className="flex gap-[22px] border-b border-[#1e2621] pb-[10px]">
        <div
          onClick={() => setChartPeriod('1d')}
          className={`text-[11.5px] tracking-[0.4px] font-semibold pb-[10px] cursor-pointer ${chartPeriod === '1d' ? 'text-[#22e07a] border-b-2 border-[#22e07a] -mb-[11px]' : 'text-[#5b655d] hover:text-[#8a958c]'
            }`}>
          1D CHART
        </div>
        <div
          onClick={() => setChartPeriod('5d')}
          className={`text-[11.5px] tracking-[0.4px] font-semibold pb-[10px] cursor-pointer ${chartPeriod === '5d' ? 'text-[#22e07a] border-b-2 border-[#22e07a] -mb-[11px]' : 'text-[#5b655d] hover:text-[#8a958c]'
            }`}>
          1W CHART
        </div>
        <div
          onClick={() => setChartPeriod('1mo')}
          className={`text-[11.5px] tracking-[0.4px] font-semibold pb-[10px] cursor-pointer ${chartPeriod === '1mo' ? 'text-[#22e07a] border-b-2 border-[#22e07a] -mb-[11px]' : 'text-[#5b655d] hover:text-[#8a958c]'
            }`}>
          1M CHART
        </div>
      </div>

      <div className="bg-[#10151199] border border-[#1e2621] rounded-[10px] p-[16px] relative h-[300px] flex flex-col">
        <div className="absolute top-[14px] right-[14px] bg-[#0d1a12] border border-[#1a7a48] rounded-[6px] p-[6px_10px] text-right z-10">
          <div className="text-[9px] text-[#5b655d] tracking-[0.4px]">TARGET (ATR)</div>
          <div className="text-[14px] font-bold text-[#22e07a]">{targetPrice.toLocaleString('id-ID')}</div>
        </div>
        <div className="absolute top-[70px] right-[14px] bg-[#1a0d0d] border border-[#5c2323] rounded-[6px] p-[6px_10px] text-right z-10">
          <div className="text-[9px] text-[#5b655d] tracking-[0.4px]">STOP LOSS</div>
          <div className="text-[14px] font-bold text-[#ff5c5c]">{stopLoss.toLocaleString('id-ID')}</div>
        </div>

        <div className="flex-1 w-full relative z-0 mt-4">
          {chartData.length > 0 ? (
            <ReactApexChart options={chartOptions} series={chartData} type="candlestick" height="100%" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[#8a958c] text-[12px] animate-pulse">Loading Chart...</div>
          )}
        </div>

        <div className="absolute bottom-[1px] left-0 right-0 text-center text-[#5b655d] text-[11px] flex items-center justify-center gap-[6px]">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#22e07a" strokeWidth="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>
          Real-time Terminal Stream Active
        </div>
      </div>
    </>
  );
};
