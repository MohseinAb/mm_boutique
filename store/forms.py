from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms
from .models import Customer

class CreateUserForm(UserCreationForm):

    email = forms.EmailField(required=True)


    phone = forms.CharField(max_length=20, required=True)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=True)

    class Meta:
        model = User
        fields = ['username', 'email']

    def save(self, commit=True):

        user = super().save(commit=False)
        user.email = self.cleaned_data['email']

        if commit:
            user.save()


            Customer.objects.create(
                user=user,
                phone=self.cleaned_data['phone'],
                address=self.cleaned_data['address']
            )

        return user



class ProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['phone', 'street_address', 'city', 'zip_code']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }