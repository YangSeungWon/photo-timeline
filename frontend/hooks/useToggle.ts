import { useState, useCallback } from "react";

export const useToggle = (
  initialValue: boolean = false
): [boolean, () => void, (value?: boolean) => void] => {
  const [value, setValue] = useState<boolean>(initialValue);

  const toggle = useCallback(() => {
    setValue((prev) => !prev);
  }, []);

  const setToggle = useCallback(
    (newValue?: boolean) => {
      setValue(newValue !== undefined ? newValue : !value);
    },
    [value]
  );

  return [value, toggle, setToggle];
};
