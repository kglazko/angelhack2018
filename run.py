from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import ElementNotInteractableException
import time

driver = webdriver.Firefox()
driver.get("http://www.indeed.com")
driver.maximize_window()
assert "Indeed" in driver.title

#Login flow
login = driver.find_element_by_xpath('/html/body/div/div[1]/nav/ul[2]/li[2]/a')
login.click()
email = driver.find_element_by_xpath('//*[@id="signin_email"]')
email.send_keys("testytest1@mailinator.com")
password = driver.find_element_by_xpath('//*[@id="signin_password"]')
password.send_keys("testtest1")
submit = driver.find_element_by_xpath('/html/body/div/div/div/section/form/button')
submit.click()

#Job Search
title = driver.find_element_by_xpath('//*[@id="text-input-what"]')
title.send_keys('intern')
location = driver.find_element_by_xpath('//*[@id="text-input-where"]')
location.send_keys(Keys.COMMAND + "a")
location.send_keys(Keys.DELETE)
location.send_keys('94041')
find_submit = driver.find_element_by_xpath('/html/body/div/div[2]/div[2]/div/form/div[3]/button')
find_submit.click()

#Auto-apply
job_iter = 0
time.sleep(3)
page_iter = len(driver.find_elements_by_class_name('iaLabel'))

for job in range(0, page_iter):
    jobs = []
    time.sleep(2)
    jobs = driver.find_elements_by_class_name('iaLabel')
    print job_iter
    print page_iter
    jobs[job_iter].click()
    timeout = 5
    try:
        element_present = EC.presence_of_element_located((By.CLASS_NAME, 'indeed-apply-button-label'))
        WebDriverWait(driver, timeout).until(element_present)
        apply_button = driver.find_element_by_class_name('indeed-apply-button-label')
        apply_button.click()
        time.sleep(3)

        driver.get('https://apply.indeed.com/indeedapply/s/resumeApply')
        continue_button = driver.find_element_by_xpath('//*[@id="form-action-continue"]')
        continue_button.click()
        #driver.get('https://apply.indeed.com/indeedapply/s/resumeApply?page=1')
        time.sleep(2)
        try:
            submit_job = driver.find_element_by_xpath('//*[@id="form-action-submit"]')
            submit_job.click()
            time.sleep(2)
            driver.execute_script("window.history.go(-3)")
        except ElementNotInteractableException:
            driver.execute_script("window.history.go(-2)")
        job_iter = job_iter + 1
    except TimeoutException:
        print "Timed out waiting for page to load"
        job_iter = job_iter + 1
