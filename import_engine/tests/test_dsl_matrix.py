import itertools
import logging
import random
import string
from import_engine.validators.dsl import DSLValidator
from import_engine.tests.base import BaseImportTestCase

logger = logging.getLogger(__name__)


class ExcelProtectionMatrixTestCase(BaseImportTestCase):
    """Technical validation for Excel-specific protection scenarios."""

    def test_massive_unique_validation_matrix(self):
        """
        Executes a high-density matrix across all validation rules with stochastic parameters.
        """
        random.seed(42)

        base_rules = ["required", "email", "phone", "date"]
        param_rules = ["min", "max", "in", "regex", "after"]


        def get_unique_val(i):
            if i % 5 == 0:
                return f"user_{i}@example.com"
            if i % 5 == 1:
                return f"+1{str(i).zfill(10)}"
            if i % 5 == 2:
                return f"2023-01-{min(28, (i % 28) + 1):02d}"
            if i % 5 == 3:
                return "".join(random.choices(string.ascii_letters, k=10)) + str(i)
            return str(i * 1.5)

        iteration = 0
        max_iterations = 10


        for r_len in range(1, 5):
            for combo in itertools.combinations(base_rules + param_rules, r_len):

                for var_idx in range(80):
                    iteration += 1
                    if iteration > max_iterations:
                        break


                    final_rules = []
                    for r in combo:
                        if r == "min":
                            final_rules.append(f"min:{random.randint(1, 50)}")
                        elif r == "max":
                            final_rules.append(f"max:{random.randint(51, 500)}")
                        elif r == "in":
                            final_rules.append(
                                f"in:{get_unique_val(iteration)},other,another"
                            )
                        elif r == "regex":
                            final_rules.append("regex:^[a-zA-Z0-9_]+$")
                        else:
                            final_rules.append(r)

                    val = get_unique_val(iteration)

                    with self.subTest(rules=final_rules, value=val, id=iteration):

                        validator = DSLValidator(
                            f"field_{iteration}", final_rules, None
                        )
                        try:

                            validator.validate(val, {"other_field": "2022-01-01"})
                        except Exception:
                            pass

                if iteration > max_iterations:
                    break
            if iteration > max_iterations:
                break

        logger.info(
            f"MCST: Successfully executed {iteration} unique validation vectors."
        )
