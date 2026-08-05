import { useState } from 'react';

export function PasswordField({ id, buttonLabel = 'รหัสผ่าน', ...inputProps }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="password-field">
      <input id={id} type={visible ? 'text' : 'password'} {...inputProps} />
      <button
        type="button"
        className="password-toggle"
        disabled={inputProps.disabled}
        onClick={() => setVisible(value => !value)}
        aria-label={`${visible ? 'ซ่อน' : 'แสดง'}${buttonLabel}`}
      >
        {visible ? 'ซ่อน' : 'แสดง'}
      </button>
    </div>
  );
}
