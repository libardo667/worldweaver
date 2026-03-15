interface Props {
  size?: number;
}

export function MagicFingerLoader({ size = 36 }: Props) {
  return (
    <img
      src="/magic_finger.png"
      alt=""
      className="magic-finger-loader"
      style={{ width: size, height: size }}
    />
  );
}
