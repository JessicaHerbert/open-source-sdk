import arrow
import requests
import json

from canvas_workflow_kit import events
from canvas_workflow_kit.constants import CHANGE_TYPE
from canvas_workflow_kit.protocol import (STATUS_NOT_APPLICABLE,
                                          ClinicalQualityMeasure,
                                          ProtocolResult)
from canvas_workflow_kit.utils import send_notification
from canvas_workflow_kit.fhir import FumageHelper

class SyncTask(ClinicalQualityMeasure):
    class Meta:
        title = 'Task Notification'
        version = 'v1.0.0'
        description = 'Listens for the creation of a task and sends a notification to a webhook'
        compute_on_change_types = [CHANGE_TYPE.TASK]
        notification_only = True

    # TODO change these
    URL = 'https://webhook.site/de73cb04-077e-489d-abca-3c31f29ac28d'
    INSTANCE_NAME = 'bh-demo' # change this for the instance you are working on

    def update_fhir_task(self, fhir, task_id, payload):
        """ Given a Task ID and payload, we will add an additional comment to the Task
        and send it to the FHIR Task Update Endpoint """

        new_note = {
            "authorReference": {
                "reference": payload['requester']['reference']
            },
            "time": f'{arrow.now()}',
            "text": (f"Task successfuly synced with the Hub: {self.URL}/{self.patient.patient_key}/view")
        }

        if payload.get('note'):
            payload['note'].append(new_note)
        else:
            payload.update({'note': [new_note]})

        fhir.update("Task", task_id, payload)


    def compute_results(self):
        result = ProtocolResult()

        # lets only check and send notification if the Task is created for the first time
        if self.field_changes.get('model_name') == 'task' and self.field_changes.get('created'):

            # field changes will contain the Task ID we can use in FHIR
            task_id = self.field_changes.get('external_id')

            fhir = FumageHelper(self.settings)

            response = fhir.search("Task", {"_id": task_id})
            if response.status_code != 200:
                raise Exception(f"Failed to find task {task_id} {response.text} {response.headers}")

            fhir_response = response.json()['entry'][0]['resource']

            # Build the payload we want sent to our webhook
            # We are demoing what a Task looks like in both FHIR and our SDK
            payload = {
                'patient_key': self.patient.patient['key'],
                'patient_name': f"{self.patient.patient['firstName']} {self.patient.patient['lastName']}",
                'fhir_response': fhir_response,
                'sdk_object': self.patient.tasks.filter(externallyExposableId=task_id)[0]
            }
            notification_response = send_notification(
                self.URL, json.dumps(payload), {'Content-Type': 'application/json'})

            if notification_response.status_code == 200:
                # We want to update the task with a comment that the payload was successfully sent
                self.update_fhir_task(fhir, task_id, fhir_response)

        return result
