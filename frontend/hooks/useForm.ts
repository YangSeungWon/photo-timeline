import { useState, useCallback } from "react";

interface ValidationRule {
  required?: boolean | string;
  minLength?: { value: number; message: string };
  maxLength?: { value: number; message: string };
  pattern?: { value: RegExp; message: string };
  custom?: (value: any) => string | undefined;
}

interface ValidationRules {
  [key: string]: ValidationRule;
}

interface FormState<T> {
  values: T;
  errors: Partial<Record<keyof T, string>>;
  touched: Partial<Record<keyof T, boolean>>;
  isSubmitting: boolean;
  isValid: boolean;
}

export const useForm = <T extends Record<string, any>>(
  initialValues: T,
  validationRules?: ValidationRules
) => {
  const [formState, setFormState] = useState<FormState<T>>({
    values: initialValues,
    errors: {},
    touched: {},
    isSubmitting: false,
    isValid: true,
  });

  const validateField = useCallback(
    (name: keyof T, value: any): string | undefined => {
      const rules = validationRules?.[name as string];
      if (!rules) return undefined;

      // Required validation
      if (rules.required) {
        const message =
          typeof rules.required === "string"
            ? rules.required
            : `${String(name)} is required`;
        if (!value || (typeof value === "string" && value.trim() === "")) {
          return message;
        }
      }

      // Skip other validations if value is empty and not required
      if (!value || (typeof value === "string" && value.trim() === "")) {
        return undefined;
      }

      // MinLength validation
      if (rules.minLength && value.length < rules.minLength.value) {
        return rules.minLength.message;
      }

      // MaxLength validation
      if (rules.maxLength && value.length > rules.maxLength.value) {
        return rules.maxLength.message;
      }

      // Pattern validation
      if (rules.pattern && !rules.pattern.value.test(value)) {
        return rules.pattern.message;
      }

      // Custom validation
      if (rules.custom) {
        return rules.custom(value);
      }

      return undefined;
    },
    [validationRules]
  );

  const validateAll = useCallback((): boolean => {
    const newErrors: Partial<Record<keyof T, string>> = {};
    let isValid = true;

    Object.keys(formState.values).forEach((key) => {
      const error = validateField(
        key as keyof T,
        formState.values[key as keyof T]
      );
      if (error) {
        newErrors[key as keyof T] = error;
        isValid = false;
      }
    });

    setFormState((prev) => ({
      ...prev,
      errors: newErrors,
      isValid,
    }));

    return isValid;
  }, [formState.values, validateField]);

  const setValue = useCallback(
    (name: keyof T, value: any) => {
      setFormState((prev) => {
        const newValues = { ...prev.values, [name]: value };
        const error = validateField(name, value);
        const newErrors = { ...prev.errors };

        if (error) {
          newErrors[name] = error;
        } else {
          delete newErrors[name];
        }

        const isValid = Object.keys(newErrors).length === 0;

        return {
          ...prev,
          values: newValues,
          errors: newErrors,
          touched: { ...prev.touched, [name]: true },
          isValid,
        };
      });
    },
    [validateField]
  );

  const setError = useCallback((name: keyof T, error: string) => {
    setFormState((prev) => ({
      ...prev,
      errors: { ...prev.errors, [name]: error },
      isValid: false,
    }));
  }, []);

  const setTouched = useCallback((name: keyof T, touched: boolean = true) => {
    setFormState((prev) => ({
      ...prev,
      touched: { ...prev.touched, [name]: touched },
    }));
  }, []);

  const setSubmitting = useCallback((isSubmitting: boolean) => {
    setFormState((prev) => ({
      ...prev,
      isSubmitting,
    }));
  }, []);

  const reset = useCallback(() => {
    setFormState({
      values: initialValues,
      errors: {},
      touched: {},
      isSubmitting: false,
      isValid: true,
    });
  }, [initialValues]);

  const getFieldProps = useCallback(
    (name: keyof T) => ({
      id: String(name),
      name: String(name),
      value: formState.values[name] || "",
      onChange: (value: any) => setValue(name, value),
      error: formState.touched[name] ? formState.errors[name] : undefined,
      onBlur: () => setTouched(name, true),
    }),
    [
      formState.values,
      formState.errors,
      formState.touched,
      setValue,
      setTouched,
    ]
  );

  return {
    values: formState.values,
    errors: formState.errors,
    touched: formState.touched,
    isSubmitting: formState.isSubmitting,
    isValid: formState.isValid,
    setValue,
    setError,
    setTouched,
    setSubmitting,
    validateAll,
    reset,
    getFieldProps,
  };
};
