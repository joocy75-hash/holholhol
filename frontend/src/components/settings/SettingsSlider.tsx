'use client';

interface SettingsSliderProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  showDivider?: boolean;
  disabled?: boolean;
}

export default function SettingsSlider({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  showDivider = true,
  disabled = false,
}: SettingsSliderProps) {
  return (
    <div
      style={{
        padding: '16px',
        borderBottom: showDivider ? '1px solid rgba(255,255,255,0.1)' : 'none',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '12px',
        }}
      >
        <p style={{ margin: 0, color: 'white', fontSize: '15px', fontWeight: 500 }}>
          {label}
        </p>
        <span
          style={{
            color: 'var(--figma-balance-color)',
            fontSize: '14px',
            fontWeight: 600,
          }}
        >
          {value}%
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        disabled={disabled}
        style={{
          width: '100%',
          height: '6px',
          borderRadius: '3px',
          background: `linear-gradient(to right, var(--figma-balance-color) ${value}%, rgba(255,255,255,0.2) ${value}%)`,
          outline: 'none',
          cursor: disabled ? 'not-allowed' : 'pointer',
          WebkitAppearance: 'none',
        }}
      />
    </div>
  );
}
